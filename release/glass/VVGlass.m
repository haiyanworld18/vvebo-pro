#import "GlassTypes.h"

// Confined to the app's existing BlurView underneath BaseBarView. No Swift
// metadata, raw ivars, original geometry, touch handlers or paid state.
// B adds a temporary, non-interactive status label for this test only.
static Class glassClass, blurClass, effectViewClass, blurViewClass, barClass;
static Class plainViewClass, cornerClass, blurButtonClass;
static IMP originalLayout, originalStyle;
static BOOL installed;
static char priorEffectKey;
static char priorHiddenKey, priorCornerKey;
static NSUInteger replacementCount;
static NSString *statusReason = @"适配尚未执行";
static UILabel *statusLabel;

static BOOL IsBarBackground(UIView *view) {
    UIView *ancestor = view.superview;
    for (unsigned depth = 0; ancestor && depth < 12; depth++) {
        if ([ancestor isKindOfClass:barClass]) return YES;
        if (blurButtonClass && [ancestor isKindOfClass:blurButtonClass]) return NO;
        ancestor = ancestor.superview;
    }
    return NO;
}

// G adds an empty, non-interactive plain UIView above each blur material.
// Its dynamic background provider commonly returns an alpha-0.8 color.
// Only hide this structural color plate when our own glass is present.
static void UpdateColorPlates(UIView *container, BOOL glassPresent) {
    NSArray *children = container.subviews;
    for (NSUInteger index = 0; index < children.count && index < 32; index++) {
        UIView *child = [children objectAtIndex:index];
        if (object_getClass(child) != plainViewClass) continue;
        id prior = objc_getAssociatedObject(child, &priorHiddenKey);
        if (!glassPresent) {
            if (prior) {
                child.hidden = [prior boolValue];
                objc_setAssociatedObject(child, &priorHiddenKey, nil, 1);
            }
        } else if (!child.isUserInteractionEnabled && child.subviews.count == 0 && child.backgroundColor) {
            if (!prior) objc_setAssociatedObject(child, &priorHiddenKey,
                [NSNumber numberWithBool:child.isHidden], 1);
            child.hidden = YES;
        }
    }
}

static void UpdateEffectChildren(UIView *view, BOOL enabled, unsigned depth, unsigned *budget) {
    NSArray *children = view.subviews;
    NSUInteger count = children.count;
    BOOL glassPresent = NO;
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
            if ([current isKindOfClass:glassClass] && prior) {
                effectView.effect = prior;
                if ([effectView respondsToSelector:sel_registerName("setCornerConfiguration:")])
                    effectView.cornerConfiguration = objc_getAssociatedObject(effectView, &priorCornerKey);
            }
            objc_setAssociatedObject(effectView, &priorEffectKey, nil, 1);
            objc_setAssociatedObject(effectView, &priorCornerKey, nil, 1);
            continue;
        }
        if ([current isKindOfClass:glassClass] && objc_getAssociatedObject(effectView, &priorEffectKey)) {
            glassPresent = YES;
            continue;
        }
        if (![current isKindOfClass:blurClass]) continue;
        id glass = [glassClass effectWithStyle:0]; // UIGlassEffectStyleRegular
        if (!glass || ![glass isKindOfClass:glassClass]) continue;
        if (!objc_getAssociatedObject(effectView, &priorEffectKey) && cornerClass &&
            [effectView respondsToSelector:sel_registerName("cornerConfiguration")])
            objc_setAssociatedObject(effectView, &priorCornerKey, effectView.cornerConfiguration, 1);
        objc_setAssociatedObject(effectView, &priorEffectKey, current, 1);
        effectView.effect = glass;
        if (cornerClass && [effectView respondsToSelector:sel_registerName("setCornerConfiguration:")])
            effectView.cornerConfiguration = [cornerClass capsuleConfiguration];
        replacementCount++;
        glassPresent = YES;
    }
    UpdateColorPlates(view, glassPresent);
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
    if (![[NSBundle mainBundle].bundleIdentifier isEqualToString:@"com.johnil.vvebo"]) {
        statusReason = @"应用标识被签名工具改变，适配未启用"; return;
    }
    if ([NSProcessInfo processInfo].operatingSystemVersion.majorVersion < 26) {
        statusReason = @"系统低于 iOS 26，保留原效果"; return;
    }
    glassClass = NSClassFromString(@"UIGlassEffect");
    blurClass = NSClassFromString(@"UIBlurEffect");
    effectViewClass = NSClassFromString(@"UIVisualEffectView");
    blurViewClass = NSClassFromString(@"_TtC5VVebo8BlurView");
    barClass = NSClassFromString(@"_TtC5VVebo11BaseBarView");
    plainViewClass = NSClassFromString(@"UIView");
    cornerClass = NSClassFromString(@"UICornerConfiguration");
    blurButtonClass = NSClassFromString(@"_TtC5VVebo10BlurButton");
    if (cornerClass && ![cornerClass respondsToSelector:sel_registerName("capsuleConfiguration")]) cornerClass = (Class)0;
    if (!glassClass || !blurClass || !effectViewClass || !blurViewClass || !barClass ||
        !plainViewClass || ![glassClass respondsToSelector:sel_registerName("effectWithStyle:")]) {
        statusReason = @"未找到玻璃接口或原浮动栏，适配未启用"; return;
    }
    SEL layout = sel_registerName("layoutSubviews");
    SEL style = sel_registerName("updateAppStyle:");
    Method layoutMethod = class_getInstanceMethod(blurViewClass, layout);
    Method styleMethod = class_getInstanceMethod(blurViewClass, style);
    if (!layoutMethod || !styleMethod) { statusReason = @"浮动栏方法不匹配"; return; }
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
    statusReason = @"未找到可替换背景";
    NSArray *windows = [UIApplication sharedApplication].windows;
    unsigned budget = 1024;
    for (NSUInteger index = 0; index < windows.count && budget; index++)
        RefreshExisting([windows objectAtIndex:index], 0, &budget);
}

static void HideStatus(void *context) {
    (void)context;
    [statusLabel removeFromSuperview];
    statusLabel = nil;
}

static void ShowStatus(void *context) {
    (void)context;
    // One test-only message, not a persistent overlay, timer or frame callback.
    NSArray *windows = [UIApplication sharedApplication].windows;
    UIView *window = nil;
    unsigned budget = 1024;
    for (NSUInteger index = 0; index < windows.count && budget; index++) {
        UIView *candidate = [windows objectAtIndex:index];
        if (installed) RefreshExisting(candidate, 0, &budget);
        if (!window && !candidate.isHidden) window = candidate;
    }
    if (!window) return;
    NSString *message;
    if (UIAccessibilityIsReduceTransparencyEnabled()) message = @"玻璃 B：系统开启了降低透明度";
    else if (replacementCount) message = [NSString stringWithFormat:@"玻璃 B：已执行 %lu 次背景替换", replacementCount];
    else message = [NSString stringWithFormat:@"玻璃 B：%@", statusReason];
    CGRect bounds = window.bounds;
    if (bounds.size.width < 100) return;
    statusLabel = [[NSClassFromString(@"UILabel") alloc] initWithFrame:
        (CGRect){{16, 100}, {bounds.size.width - 32, 70}}];
    statusLabel.text = message;
    statusLabel.numberOfLines = 3;
    statusLabel.textAlignment = 1;
    statusLabel.userInteractionEnabled = NO;
    statusLabel.backgroundColor = [NSClassFromString(@"UIColor") secondarySystemBackgroundColor];
    statusLabel.textColor = [NSClassFromString(@"UIColor") labelColor];
    [window addSubview:statusLabel];
    dispatch_after_f(dispatch_time(0, 5000000000LL), &_dispatch_main_q, (void *)0, HideStatus);
}

static void InstallAndReport(void *context) {
    InstallGlass(context);
    dispatch_after_f(dispatch_time(0, 2000000000LL), &_dispatch_main_q, (void *)0, ShowStatus);
}

__attribute__((constructor)) static void StartGlass(void) {
    // Wait until the main thread can safely realize the app's Swift/ObjC views.
    // Do not initialize UIKit or Swift classes inside the dyld loader callback.
    dispatch_async_f(&_dispatch_main_q, (void *)0, InstallAndReport);
}
