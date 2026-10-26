// Public SDK declarations only. Implementations are supplied by iOS.
#import "../network/AppleTypes.h"
typedef struct { NSInteger majorVersion, minorVersion, patchVersion; } NSOperatingSystemVersion;
@interface NSProcessInfo : NSObject
+ (NSProcessInfo *)processInfo;
@property(readonly) NSOperatingSystemVersion operatingSystemVersion;
@end
@interface NSThread : NSObject
+ (BOOL)isMainThread;
@end
@interface UIView : NSObject
- (id)initWithFrame:(CGRect)frame;
@property(readonly) UIView *superview;
@property(readonly) NSArray *subviews;
@property(readonly) CGRect bounds;
@property(getter=isHidden) BOOL hidden;
@property(getter=isUserInteractionEnabled) BOOL userInteractionEnabled;
@property(strong) id backgroundColor;
@property(strong) id cornerConfiguration;
- (void)addSubview:(UIView *)view;
- (void)removeFromSuperview;
@end
@interface UILabel : UIView
@property(copy) NSString *text;
@property(strong) id textColor;
@property NSInteger textAlignment;
@property NSInteger numberOfLines;
@end
@interface NSNumber (VVGlassNumbers)
+ (NSNumber *)numberWithBool:(BOOL)value;
@end
@interface UIVisualEffectView : UIView
@property(strong) id effect;
@end
@interface UIApplication : NSObject
+ (UIApplication *)sharedApplication;
@property(readonly) NSArray *windows;
@end
@interface NSObject (VVGlassFactory)
+ (id)effectWithStyle:(NSInteger)style;
+ (id)capsuleConfiguration;
+ (id)secondarySystemBackgroundColor;
+ (id)labelColor;
@end
extern BOOL UIAccessibilityIsReduceTransparencyEnabled(void);
extern struct dispatch_queue_s _dispatch_main_q;
extern void dispatch_async_f(struct dispatch_queue_s *, void *, void (*)(void *));
extern long long dispatch_time(long long, long long);
extern void dispatch_after_f(long long, struct dispatch_queue_s *, void *, void (*)(void *));
