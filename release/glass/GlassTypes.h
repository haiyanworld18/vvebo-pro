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
@property(readonly) UIView *superview;
@property(readonly) NSArray *subviews;
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
@end
extern BOOL UIAccessibilityIsReduceTransparencyEnabled(void);
extern struct dispatch_queue_s _dispatch_main_q;
extern void dispatch_async_f(struct dispatch_queue_s *, void *, void (*)(void *));
