#import "GlassTypes.h"

// Confined to the app's existing BlurView underneath BaseBarView. No Swift
// metadata, raw ivars, original geometry, touch handlers or paid state.
// D adds a temporary status label and native material comparison card.
static Class glassClass, blurClass, effectViewClass, blurViewClass, barClass;
static Class plainViewClass, cornerClass, blurButtonClass;
static IMP originalLayout, originalStyle;
static BOOL installed;
static char freshSurfaceKey;
static char priorHiddenKey, priorEffectHiddenKey;
static NSUInteger replacementCount;
static NSString *statusReason = @"适配尚未执行";
static UILabel *statusLabel;
static UIView *comparisonCard;

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

// Build a fresh UIVisualEffectView with UIGlassEffect at initialization. The
// old effect object is never changed; its original visibility is reversible.
static void UpdateEffectChildren(UIView *view, BOOL enabled, unsigned depth, unsigned *budget) {
    NSArray *children = view.subviews;
    NSUInteger count = children.count;
    BOOL glassPresent = NO;
    for (NSUInteger index = 0; index < count && *budget; index++) {
        --*budget;
        id child = [children objectAtIndex:index];
        if (![child isKindOfClass:effectViewClass]) {
            if (depth < 2 && ![child isKindOfClass:blurViewClass])
                UpdateEffectChildren(child, enabled, depth + 1, budget);
            continue;
        }
        UIVisualEffectView *oldView = child;
        if (![oldView.effect isKindOfClass:blurClass]) continue;
        UIVisualEffectView *newView = objc_getAssociatedObject(oldView, &freshSurfaceKey);
        if (!enabled) {
            if (newView) {
                [newView removeFromSuperview];
                id prior = objc_getAssociatedObject(oldView, &priorEffectHiddenKey);
                if (prior) oldView.hidden = [prior boolValue];
                objc_setAssociatedObject(oldView, &freshSurfaceKey, nil, 1);
                objc_setAssociatedObject(oldView, &priorEffectHiddenKey, nil, 1);
            }
            continue;
        }
        if (!newView) {
            id glass = [glassClass effectWithStyle:1]; // public clear glass style
            if (!glass || ![glass isKindOfClass:glassClass]) continue;
            newView = [[effectViewClass alloc] initWithEffect:glass];
            if (!newView) continue;
            newView.userInteractionEnabled = NO;
            newView.autoresizingMask = 18; // flexible width + height, as in G
            if (cornerClass && [newView respondsToSelector:sel_registerName("setCornerConfiguration:")])
                newView.cornerConfiguration = [cornerClass capsuleConfiguration];
            objc_setAssociatedObject(oldView, &priorEffectHiddenKey,
                                     [NSNumber numberWithBool:oldView.isHidden], 1);
            objc_setAssociatedObject(oldView, &freshSurfaceKey, newView, 1);
            newView.frame = oldView.frame;
            [view insertSubview:newView atIndex:0];
            replacementCount++;
        }
        newView.frame = oldView.frame;
        oldView.hidden = YES;
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
    [comparisonCard removeFromSuperview];
    comparisonCard = nil;
}

static UILabel *MakeLabel(CGRect frame, NSString *text) {
    UILabel *label = [[NSClassFromString(@"UILabel") alloc] initWithFrame:frame];
    label.text = text;
    label.numberOfLines = 2;
    label.textAlignment = 1;
    label.userInteractionEnabled = NO;
    label.textColor = [NSClassFromString(@"UIColor") labelColor];
    return label;
}

// Native effects over the same synthetic colored backdrop. This temporary
// card is a visual control; drawing the card does not prove native rendering.
static void ShowComparison(UIView *window) {
    if (!installed || UIAccessibilityIsReduceTransparencyEnabled()) return;
    CGFloat width = window.bounds.size.width - 32;
    if (width < 200) return;
    comparisonCard = [[plainViewClass alloc] initWithFrame:(CGRect){{16, 174}, {width, 158}}];
    comparisonCard.userInteractionEnabled = NO;
    comparisonCard.backgroundColor = [NSClassFromString(@"UIColor") secondarySystemBackgroundColor];
    [comparisonCard addSubview:MakeLabel((CGRect){{0, 0}, {width, 30}}, @"左：原模糊    右：原生玻璃")];
    const double colors[4][3] = {{0.12, 0.40, 0.95}, {0.95, 0.30, 0.24},
                                  {0.20, 0.75, 0.40}, {0.95, 0.65, 0.15}};
    for (unsigned index = 0; index < 8; index++) {
        UIView *stripe = [[plainViewClass alloc] initWithFrame:
            (CGRect){{width * index / 8, 30}, {width / 8, 128}}];
        stripe.userInteractionEnabled = NO;
        stripe.backgroundColor = [NSClassFromString(@"UIColor") colorWithRed:colors[index % 4][0]
            green:colors[index % 4][1] blue:colors[index % 4][2] alpha:1];
        [stripe addSubview:MakeLabel((CGRect){{0, 0}, {width / 8, 128}}, @"ABC\n123")];
        [comparisonCard addSubview:stripe];
    }
    for (unsigned index = 0; index < 2; index++) {
        id effect = index ? [glassClass effectWithStyle:1] : [blurClass effectWithStyle:1];
        if (!effect) continue;
        UIVisualEffectView *surface = [[effectViewClass alloc] initWithEffect:effect];
        surface.frame = (CGRect){{8 + index * width / 2, 56}, {width / 2 - 16, 76}};
        surface.userInteractionEnabled = NO;
        if (cornerClass && [surface respondsToSelector:sel_registerName("setCornerConfiguration:")])
            surface.cornerConfiguration = [cornerClass capsuleConfiguration];
        [surface.contentView addSubview:MakeLabel((CGRect){{0, 0}, {width / 2 - 16, 76}},
                                                 index ? @"原生玻璃" : @"原模糊")];
        [comparisonCard addSubview:surface];
    }
    [window addSubview:comparisonCard];
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
    if (UIAccessibilityIsReduceTransparencyEnabled()) message = @"玻璃 D：系统开启了降低透明度";
    else if (replacementCount) message = [NSString stringWithFormat:@"玻璃 D：已新建 %lu 处玻璃背景", replacementCount];
    else message = [NSString stringWithFormat:@"玻璃 D：%@", statusReason];
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
    ShowComparison(window);
    dispatch_after_f(dispatch_time(0, 12000000000LL), &_dispatch_main_q, (void *)0, HideStatus);
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
