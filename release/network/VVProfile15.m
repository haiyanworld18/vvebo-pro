#import "AppleTypes.h"
// iOS 15 baseline experiment. Request/response mapping follows the user-provided QX script.
// No custom Objective-C classes, raw ivars, window hooks, or per-class object storage.
static NSString *lastProfileUID;
static char responseBufferKey;

typedef id (^ImplementationBuilder)(IMP next);
typedef struct { const void *owner; SEL selector; IMP replacement; IMP next; } HookRecord;
static HookRecord installed[64];
static unsigned int installedCount;
static unsigned char installationLock;
static void Lock(void) { while(__atomic_test_and_set(&installationLock,__ATOMIC_ACQUIRE)) {} }
static void Unlock(void) { __atomic_clear(&installationLock,__ATOMIC_RELEASE); }

// Each runtime block captures the exact previous IMP. No lookup by the receiver's
// dynamic class is performed when calling the previous method.
static BOOL Install(Class cls,SEL selector,ImplementationBuilder builder,IMP *outNext) {
    if(!cls) return NO;
    Lock();
    Method method=class_getInstanceMethod(cls,selector);
    if(!method) { Unlock();return NO; }
    IMP current=method_getImplementation(method);
    for(unsigned int i=0;i<installedCount;i++) {
        if(installed[i].owner==(__bridge const void*)cls && installed[i].selector==selector && installed[i].replacement==current) {
            if(outNext) *outNext=installed[i].next;
            Unlock();return YES;
        }
    }
    if(installedCount==64) { Unlock();return NO; }
    id block=builder(current);
    IMP replacement=imp_implementationWithBlock(block);
    if(!replacement) { Unlock();return NO; }
    const char *types=method_getTypeEncoding(method);
    installed[installedCount++]=(HookRecord){(__bridge const void*)cls,selector,replacement,current};
    if(!class_addMethod(cls,selector,replacement,types)) class_replaceMethod(cls,selector,replacement,types);
    if(outNext) *outNext=current;
    Unlock();return YES;
}

static BOOL IsWeibo(NSURL *url) {
    return [url.scheme isEqualToString:@"https"] && [url.host isEqualToString:@"api.weibo.cn"];
}
static BOOL NumericUID(NSString *uid) {
    // Existing requests carry numeric IDs. Empty or unexpected types are not rewritten.
    return [uid isKindOfClass:[NSString class]] && [uid integerValue]>0;
}
static NSURLRequest *Rewrite(NSURLRequest *request,BOOL *changed) {
    *changed=NO;
    NSURL *url=request.URL;
    if(!IsWeibo(url)) return request;
    BOOL isUser=[url.path isEqualToString:@"/2/users/show"];
    BOOL isTimeline=[url.path isEqualToString:@"/2/statuses/user_timeline"];
    if(!isUser && !isTimeline) return request;
    NSURLComponents *parts=[NSURLComponents componentsWithURL:url resolvingAgainstBaseURL:NO];
    NSString *uid=nil;
    for(NSUInteger i=0;i<parts.queryItems.count;i++) {
        NSURLQueryItem *q=[parts.queryItems objectAtIndex:i];
        if([q.name isEqualToString:@"uid"] && NumericUID(q.value)) uid=q.value;
    }
    @synchronized([NSURLSession class]) {
        if(uid) lastProfileUID=[uid copy];
        else if(isTimeline) uid=lastProfileUID;
    }
    if(!isTimeline || !uid) return request;
    NSMutableArray *items=[NSMutableArray array];
    for(NSUInteger i=0;i<parts.queryItems.count;i++) {
        NSURLQueryItem *q=[parts.queryItems objectAtIndex:i];
        if([q.name isEqualToString:@"containerid"]) continue;
        if([q.name isEqualToString:@"max_id"]) q=[NSURLQueryItem queryItemWithName:@"since_id" value:q.value];
        [items addObject:q];
    }
    [items addObject:[NSURLQueryItem queryItemWithName:@"containerid" value:[NSString stringWithFormat:@"230413%@_-_WEIBO_SECOND_PROFILE_WEIBO",uid]]];
    parts.path=@"/2/profile/statuses/tab";
    parts.queryItems=items;
    if(!parts.URL) return request;
    NSMutableURLRequest *copy=[request mutableCopy]; copy.URL=parts.URL;
    *changed=YES; return copy;
}
static NSData *Convert(NSData *input,NSURLResponse *response,NSError *error) {
    if(error || !input.length) return input;
    if([response isKindOfClass:[NSHTTPURLResponse class]]) {
        NSInteger status=((NSHTTPURLResponse*)response).statusCode;
        if(status<200 || status>=300) return input;
    }
    NSError *jsonError=nil;
    id root=[NSJSONSerialization JSONObjectWithData:input options:0 error:&jsonError];
    if(jsonError || ![root isKindOfClass:[NSDictionary class]]) return input;
    id cards=[root objectForKey:@"cards"];
    if(![cards isKindOfClass:[NSArray class]]) return input;
    NSMutableArray *statuses=[NSMutableArray array];
    for(NSUInteger i=0;i<[cards count];i++) {
        id card=[cards objectAtIndex:i];
        if(![card isKindOfClass:[NSDictionary class]]) continue;
        id group=[card objectForKey:@"card_group"];
        NSArray *entries=[group isKindOfClass:[NSArray class]] ? group : @[card];
        for(NSUInteger j=0;j<entries.count;j++) {
            id entry=[entries objectAtIndex:j];
            if(![entry isKindOfClass:[NSDictionary class]]) continue;
            id type=[entry objectForKey:@"card_type"];
            if(![type respondsToSelector:sel_registerName("integerValue")] || [type integerValue]!=9) continue;
            id post=[entry objectForKey:@"mblog"];
            if(![post isKindOfClass:[NSDictionary class]]) continue;
            id top=[post objectForKey:@"isTop"];
            if([top respondsToSelector:sel_registerName("boolValue")] && [top boolValue]) {
                NSMutableDictionary *p=[post mutableCopy]; p[@"label"]=@"置顶"; post=p;
            }
            [statuses addObject:post];
        }
    }
    NSMutableDictionary *result=[NSMutableDictionary dictionary];
    result[@"statuses"]=statuses; result[@"total_number"]=@100;
    id info=[root objectForKey:@"cardlistInfo"];
    if([info isKindOfClass:[NSDictionary class]]) {
        id since=[info objectForKey:@"since_id"];
        if(since) result[@"since_id"]=since;
    }
    NSData *output=[NSJSONSerialization dataWithJSONObject:result options:0 error:&jsonError];
    return output && !jsonError ? output : input;
}

@interface NSURLSession (ProfileAdapterDelegate)
@property(readonly) id delegate;
@end

typedef void (*DelegateCallback)(id,SEL,id,id,id);
typedef id (*TaskCreator)(id,SEL,NSURLRequest*);
typedef void (^DataCompletion)(NSData*,NSURLResponse*,NSError*);
typedef id (*CompletionTaskCreator)(id,SEL,NSURLRequest*,DataCompletion);
typedef id (*SessionCreator)(id,SEL,id,id,id);

static BOOL PrepareDelegate(id delegate) {
    Class cls=object_getClass(delegate);
    SEL received=sel_registerName("URLSession:dataTask:didReceiveData:");
    SEL completed=sel_registerName("URLSession:task:didCompleteWithError:");
    if(!cls || !class_getInstanceMethod(cls,received) || !class_getInstanceMethod(cls,completed)) return NO;
    IMP dataNext=(IMP)0;
    BOOL receiveInstalled=Install(cls,received,^id(IMP next) {
        return [^(id receiver,id session,NSURLSessionTask *task,NSData *chunk) {
            NSMutableData *buffer=objc_getAssociatedObject(task,&responseBufferKey);
            if(buffer) { @synchronized(buffer) { [buffer appendData:chunk]; } return; }
            ((DelegateCallback)next)(receiver,received,session,task,chunk);
        } copy];
    },&dataNext);
    if(!receiveInstalled || !dataNext) return NO;
    return Install(cls,completed,^id(IMP next) {
        return [^(id receiver,id session,NSURLSessionTask *task,NSError *error) {
            NSMutableData *buffer=objc_getAssociatedObject(task,&responseBufferKey);
            if(buffer) {
                NSData *data;
                @synchronized(buffer) { data=[buffer copy]; }
                objc_setAssociatedObject(task,&responseBufferKey,nil,1);
                if(data.length) ((DelegateCallback)dataNext)(receiver,received,session,task,Convert(data,task.response,error));
            }
            ((DelegateCallback)next)(receiver,completed,session,task,error);
        } copy];
    },(IMP*)0);
}

static void PrepareSession(id session) {
    if(!session) return;
    PrepareDelegate([session delegate]);
    Class cls=object_getClass(session);
    SEL createTask=sel_registerName("dataTaskWithRequest:");
    Install(cls,createTask,^id(IMP next) {
        return [^id(id receiver,NSURLRequest *request) {
            BOOL changed=NO;
            NSURLRequest *updated=PrepareDelegate([receiver delegate]) ? Rewrite(request,&changed) : request;
            id task=((TaskCreator)next)(receiver,createTask,updated);
            if(changed && task) objc_setAssociatedObject(task,&responseBufferKey,[NSMutableData data],1);
            return task;
        } copy];
    },(IMP*)0);
    SEL createCompletionTask=sel_registerName("dataTaskWithRequest:completionHandler:");
    Install(cls,createCompletionTask,^id(IMP next) {
        return [^id(id receiver,NSURLRequest *request,DataCompletion completion) {
            BOOL changed=NO;NSURLRequest *updated=Rewrite(request,&changed);
            DataCompletion wrapped=completion;
            if(changed && completion) wrapped=^(NSData *data,NSURLResponse *response,NSError *error) {
                completion(Convert(data,response,error),response,error);
            };
            return ((CompletionTaskCreator)next)(receiver,createCompletionTask,updated,wrapped);
        } copy];
    },(IMP*)0);
}

__attribute__((constructor)) static void StartProfileAdapter(void) {
    @autoreleasepool {
        if(![[NSBundle mainBundle].bundleIdentifier isEqualToString:@"com.johnil.vvebo"]) return;
        SEL createSession=sel_registerName("sessionWithConfiguration:delegate:delegateQueue:");
        Install(object_getClass((id)[NSURLSession class]),createSession,^id(IMP next) {
            return [^id(id receiver,id configuration,id delegate,id queue) {
                PrepareDelegate(delegate);
                id session=((SessionCreator)next)(receiver,createSession,configuration,delegate,queue);
                PrepareSession(session);
                return session;
            } copy];
        },(IMP*)0);
        NSLog(@"[VVProfile15 A] Local profile adapter initialized.");
    }
}
