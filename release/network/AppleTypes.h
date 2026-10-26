// Minimal public Objective-C API declarations used for cross-compilation.
// This file contains declarations only; implementations come from iOS.
typedef unsigned long NSUInteger;
typedef long NSInteger;
typedef _Bool BOOL;
typedef double CGFloat;
#define nil ((id)0)
#define YES ((_Bool)1)
#define NO ((_Bool)0)
typedef struct { CGFloat x,y; } CGPoint;
typedef struct { CGFloat width,height; } CGSize;
typedef struct { CGPoint origin; CGSize size; } CGRect;
typedef struct objc_method *Method;
typedef id (*IMP)(id,SEL,...);
extern Class object_getClass(id);
extern Class class_getSuperclass(Class);
extern Method class_getInstanceMethod(Class,SEL);
extern IMP method_getImplementation(Method);
extern IMP imp_implementationWithBlock(id block);
extern const char *method_getTypeEncoding(Method);
extern BOOL class_addMethod(Class,SEL,IMP,const char*);
extern IMP class_replaceMethod(Class,SEL,IMP,const char*);
extern SEL sel_registerName(const char*);
extern id objc_getAssociatedObject(id,const void*);
extern void objc_setAssociatedObject(id,const void*,id,NSUInteger);
__attribute__((objc_root_class))
@interface NSObject { Class isa; }
+ (id)alloc; + (id)new; + (Class)class;
- (id)init; - (Class)class; - (BOOL)isKindOfClass:(Class)c;
- (BOOL)respondsToSelector:(SEL)s;
- (id)copy; - (id)mutableCopy;
@end
@class NSString,NSArray,NSMutableArray,NSDictionary,NSMutableDictionary,NSData,NSMutableData,NSURL,NSURLRequest,NSMutableURLRequest,NSURLQueryItem,NSURLComponents,NSError,NSURLResponse,NSHTTPURLResponse;
@interface NSString:NSObject
+ (id)stringWithFormat:(NSString*)format,...;
- (BOOL)isEqualToString:(NSString*)s;
- (BOOL)boolValue;
- (NSInteger)integerValue;
@end
@interface NSArray:NSObject
@property(readonly) NSUInteger count;
- (id)objectAtIndex:(NSUInteger)i;
+ (id)arrayWithObjects:(const id[])objects count:(NSUInteger)count;
@end
@interface NSMutableArray:NSArray
+ (id)array; - (void)addObject:(id)o;
@end
@interface NSDictionary:NSObject
- (id)objectForKey:(id)key;
- (id)objectForKeyedSubscript:(id)key;
+ (id)dictionaryWithObjects:(const id[])objects forKeys:(const id[])keys count:(NSUInteger)n;
@end
@interface NSMutableDictionary:NSDictionary
+ (id)dictionary;
- (void)setObject:(id)o forKey:(id)key;
- (void)setObject:(id)o forKeyedSubscript:(id)key;
@end
@interface NSValue:NSObject
+ (id)valueWithPointer:(const void*)pointer;
- (void*)pointerValue;
@end
@interface NSNumber:NSObject
+ (id)numberWithInt:(int)n;
- (BOOL)boolValue; - (NSInteger)integerValue;
@end
@interface NSData:NSObject
@property(readonly) NSUInteger length;
@end
@interface NSMutableData:NSData
+ (id)data;
- (void)appendData:(NSData*)d;
@end
@interface NSJSONSerialization:NSObject
+ (id)JSONObjectWithData:(NSData*)d options:(NSUInteger)o error:(NSError* __autoreleasing*)e;
+ (NSData*)dataWithJSONObject:(id)obj options:(NSUInteger)o error:(NSError* __autoreleasing*)e;
@end
@interface NSURL:NSObject
@property(readonly) NSString *scheme;
@property(readonly) NSString *host;
@property(readonly) NSString *path;
@end
@interface NSURLQueryItem:NSObject
@property(readonly) NSString *name;
@property(readonly) NSString *value;
+ (id)queryItemWithName:(NSString*)name value:(NSString*)value;
@end
@interface NSURLComponents:NSObject
+ (id)componentsWithURL:(NSURL*)url resolvingAgainstBaseURL:(BOOL)resolve;
@property(copy) NSString *path;
@property(copy) NSArray *queryItems;
@property(readonly) NSURL *URL;
@end
@interface NSURLRequest:NSObject
@property(readonly) NSURL *URL;
@end
@interface NSMutableURLRequest:NSURLRequest
@property(copy) NSURL *URL;
@end
@interface NSURLResponse:NSObject
@end
@interface NSHTTPURLResponse:NSURLResponse
@property(readonly) NSInteger statusCode;
@end
@interface NSURLSessionTask:NSObject
@property(readonly) NSURLResponse *response;
@end
@interface NSURLSession:NSObject
@end
@interface NSBundle:NSObject
+ (NSBundle*)mainBundle;
@property(readonly) NSString *bundleIdentifier;
- (id)objectForInfoDictionaryKey:(NSString*)key;
@end
@protocol UICoordinateSpace
@property(readonly) CGRect bounds;
@end
@interface UIWindowScene:NSObject
@property(readonly) id<UICoordinateSpace> coordinateSpace;
@end
@interface UIWindow:NSObject
@property CGRect frame;
@property(readonly) UIWindowScene *windowScene;
@property(readonly) CGFloat windowLevel;
@property(readonly) id rootViewController;
@end
extern Class NSClassFromString(NSString*);
extern void NSLog(NSString*,...);
