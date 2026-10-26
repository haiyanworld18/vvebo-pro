#import "GlassTypes.h"

// Confined to the app's existing BlurView underneath BaseBarView. No Swift
// metadata, raw ivars, view insertion, geometry, touch handlers or paid state.
static Class glassClass, blurClass, effectViewClass, blurViewClass, barClass;
static IMP originalLayout, originalStyle;
static BOOL installed;
static char priorEffectKey;

static BOOL IsBarBackground(UIView *view) {
    UIView *ancestor = view.superview;
    for (unsigned depth = 0; ancestor && depth < 12; depth++) {
        if ([ancestor isKindOfClass:barClass]) return YES;
        ancestor = ancestor.superview;
    }
    return NO;
}

static void UpdateEffectChildren(UIView *view, BOOL enabled, unsigned depth, unsigned *budget) {
    NSArray *children = view.subviews;
    NSUInteger count = children.count;
    for (NSUInteger index = 0; index < count && *budget; index++) {
        --*budget;
        id child = [children objectAtIndex:index];
        if (![child isKindOfClass:effectViewClass]) {
            // G's effect view is inside a plain UIView owned by BlurView.
            // Do not enter another BlurView or UIKit's internal effect subviews.
            if (depth < 2 && ![child isKindOfClass:blurViewClass])
                UpdateEffectChildren(child, enabled, depth + 1, budget);
            continue;
        }
        UIVisualEffectView *effectView = child;
        id current = effectView.effect;
        if (!enabled) {
            id prior = objc_getAssociatedObject(effectView, &priorEffectKey);
            if ([current isKindOfClass:glassClass] && prior) effectView.effect = prior;
            objc_setAssociatedObject(effectView, &priorEffectKey, nil, 1);
            continue;
        }
        if (![current isKindOfClass:blurClass]) continue;
        id glass = [glassClass effectWithStyle:0]; // UIGlassEffectStyleRegular
        if (!glass || ![glass isKindOfClass:glassClass]) continue;
        objc_setAssociatedObject(effectView, &priorEffectKey, current, 1);
        effectView.effect = glass;
    }
}

__attribute__((used, noinline))
static void ApplyGlass(UIView *view) {
    if (![NSThread isMainThread] || !glassClass || !blurViewClass || !barClass ||
        ![view isKindOfClass:blurViewClass]) return;
    BOOL enabled = IsBarBackground(view) && !UIAccessibilityIsReduceTransparencyEnabled();
    // Only replace UIBlurEffect, never vibrancy or an unrelated screen overlay.
    unsigned budget = 32;
    UpdateEffectChildren(view, enabled, 0, &budget);
}

__attribute__((used, noinline))
static void GlassLayout(id receiver, SEL selector) {
    ((void (*)(id, SEL))originalLayout)(receiver, selector);
    ApplyGlass(receiver);
}

__attribute__((used, noinline))
static void GlassStyle(id receiver, SEL selector, id notification) {
    ((void (*)(id, SEL, id))originalStyle)(receiver, selector, notification);
    ApplyGlass(receiver);
}

// A single bounded pass catches views created before the queued installer ran.
// Later updates use only BlurView callbacks; there is no timer or frame loop.
static void RefreshExisting(UIView *view, unsigned depth, unsigned *budget) {
    if (!view || depth > 32 || !*budget) return;
    --*budget;
    ApplyGlass(view);
    NSArray *children = view.subviews;
    for (NSUInteger index = 0; index < children.count && *budget; index++)
        RefreshExisting([children objectAtIndex:index], depth + 1, budget);
}

__attribute__((used, noinline))
static void InstallGlass(void *context) {
    (void)context;
    if (installed || ![NSThread isMainThread]) return;
    if (![[NSBundle mainBundle].bundleIdentifier isEqualToString:@"com.johnil.vvebo"]) return;
    if ([NSProcessInfo processInfo].operatingSystemVersion.majorVersion < 26) return;
    glassClass = NSClassFromString(@"UIGlassEffect");
    blurClass = NSClassFromString(@"UIBlurEffect");
    effectViewClass = NSClassFromString(@"UIVisualEffectView");
    blurViewClass = NSClassFromString(@"_TtC5VVebo8BlurView");
    barClass = NSClassFromString(@"_TtC5VVebo11BaseBarView");
    if (!glassClass || !blurClass || !effectViewClass || !blurViewClass || !barClass ||
        ![glassClass respondsToSelector:sel_registerName("effectWithStyle:")]) return;
    SEL layout = sel_registerName("layoutSubviews");
    SEL style = sel_registerName("updateAppStyle:");
    Method layoutMethod = class_getInstanceMethod(blurViewClass, layout);
    Method styleMethod = class_getInstanceMethod(blurViewClass, style);
    if (!layoutMethod || !styleMethod) return;
    originalLayout = method_getImplementation(layoutMethod);
    originalStyle = method_getImplementation(styleMethod);
    if (!originalLayout || !originalStyle) return;
    // Both methods are owned by this exact class in the pinned G executable.
    // Preserve their original Objective-C type encodings and exact previous IMP.
    class_replaceMethod(blurViewClass, layout, (IMP)GlassLayout,
                        method_getTypeEncoding(layoutMethod));
    class_replaceMethod(blurViewClass, style, (IMP)GlassStyle,
                        method_getTypeEncoding(styleMethod));
    installed = YES;
    NSArray *windows = [UIApplication sharedApplication].windows;
    unsigned budget = 1024;
    for (NSUInteger index = 0; index < windows.count && budget; index++)
        RefreshExisting([windows objectAtIndex:index], 0, &budget);
}

__attribute__((constructor)) static void StartGlass(void) {
    // Wait until the main thread can safely realize the app's Swift/ObjC views.
    // Do not initialize UIKit or Swift classes inside the dyld loader callback.
    dispatch_async_f(&_dispatch_main_q, (void *)0, InstallGlass);
}
