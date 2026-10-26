#import "GlassTypes.h"

// E: UIKit's iOS 26 glass BUTTON configurations, not UIBlurEffect or a
// replacement background effect. No custom touch animation or action relay.
static Class buttonClass, configurationClass, barClass;
static IMP originalLayout;
static BOOL installed;
static char adaptedKey, createdKey;
static NSUInteger configuredCount;
static NSString *statusReason = @"原生控件适配尚未执行";
static UILabel *statusLabel;
static UIView *controlCard;

static BOOL InsideOriginalBar(UIView *view) {
    UIView *parent = view.superview;
    for (unsigned depth = 0; parent && depth < 12; depth++) {
        if ([parent isKindOfClass:barClass]) return YES;
        parent = parent.superview;
    }
    return NO;
}

// Keep the SAME original UIButton and its target/action, gestures and frame.
// Only initially unconfigured, compact icon-only buttons with real content
// inside the old bar are eligible. UIControl-based TabbarButton is not UIButton.
__attribute__((used, noinline)) static void ApplyNativeButton(UIButton *button) {
    if (!installed || ![NSThread isMainThread] || ![button isKindOfClass:buttonClass] ||
        objc_getAssociatedObject(button, &createdKey)) return;
    BOOL eligible = InsideOriginalBar(button) && !UIAccessibilityIsReduceTransparencyEnabled();
    id adapted = objc_getAssociatedObject(button, &adaptedKey);
    if (adapted) {
        if (!eligible) {
            objc_setAssociatedObject(button, &adaptedKey, nil, 1);
            button.configuration = nil; // It was nil when the adaptation began.
        }
        return;
    }
    if (!eligible || button.configuration) return;
    CGRect bounds = button.bounds;
    if (bounds.size.width < 24 || bounds.size.width > 180 ||
        bounds.size.height < 24 || bounds.size.height > 88) return;
    id image = button.currentImage;
    NSString *title = button.currentTitle;
    // Defer text/stateful follow buttons until their update behavior is inspected.
    if (!image || title) return;
    CGSize imageSize = ((UIImage *)image).size;
    if (imageSize.width > 64 || imageSize.height > 64) return; // Defer photo/avatar content.
    UIButtonConfiguration *configuration = [configurationClass glassButtonConfiguration];
    if (!configuration) return;
    configuration.title = title;
    configuration.image = image;
    configuration.cornerStyle = 4; // public UIButtonConfigurationCornerStyleCapsule
    configuration.contentInsets = (NSDirectionalEdgeInsets){0, 0, 0, 0};
    // Mark BEFORE assigning; UIKit may request layout during configuration.
    objc_setAssociatedObject(button, &adaptedKey, [NSNumber numberWithBool:YES], 1);
    button.configuration = configuration;
    configuredCount++;
}

__attribute__((used, noinline)) static void NativeButtonLayout(id receiver, SEL selector) {
    ((void (*)(id, SEL))originalLayout)(receiver, selector);
    ApplyNativeButton(receiver);
}

static void RefreshExisting(UIView *view, unsigned depth, unsigned *budget) {
    if (!view || depth > 32 || !*budget) return;
    --*budget;
    ApplyNativeButton((UIButton *)view);
    // Never descend into UIKit's private button hierarchy.
    if ([view isKindOfClass:buttonClass]) return;
    NSArray *children = view.subviews;
    for (NSUInteger index = 0; index < children.count && *budget; index++)
        RefreshExisting([children objectAtIndex:index], depth + 1, budget);
}

__attribute__((used, noinline)) static void InstallNativeButtons(void *context) {
    (void)context;
    if (installed || ![NSThread isMainThread]) return;
    if (![[NSBundle mainBundle].bundleIdentifier isEqualToString:@"com.johnil.vvebo"]) {
        statusReason = @"签名后的应用标识不同，未启用"; return;
    }
    if ([NSProcessInfo processInfo].operatingSystemVersion.majorVersion < 26) {
        statusReason = @"需要 iOS 26 原生控件接口"; return;
    }
    buttonClass = NSClassFromString(@"UIButton");
    configurationClass = NSClassFromString(@"UIButtonConfiguration");
    barClass = NSClassFromString(@"_TtC5VVebo11BaseBarView");
    if (!buttonClass || !configurationClass || !barClass ||
        ![configurationClass respondsToSelector:sel_registerName("glassButtonConfiguration")] ||
        ![configurationClass respondsToSelector:sel_registerName("prominentGlassButtonConfiguration")]) {
        statusReason = @"系统未提供所需玻璃按钮接口"; return;
    }
    SEL selector = sel_registerName("layoutSubviews");
    Method method = class_getInstanceMethod(buttonClass, selector);
    if (!method) { statusReason = @"未找到按钮布局入口"; return; }
    originalLayout = method_getImplementation(method);
    if (!originalLayout) return;
    // Add/replace on UIButton only; never mutate a superclass's Method object.
    class_replaceMethod(buttonClass, selector, (IMP)NativeButtonLayout,
                        method_getTypeEncoding(method));
    installed = YES;
    statusReason = @"原生按钮接口可用";
}

static UILabel *MakeLabel(CGRect frame, NSString *text) {
    UILabel *label = [[NSClassFromString(@"UILabel") alloc] initWithFrame:frame];
    label.text = text;
    label.numberOfLines = 3;
    label.textAlignment = 1;
    label.userInteractionEnabled = NO;
    label.textColor = [NSClassFromString(@"UIColor") labelColor];
    return label;
}

__attribute__((used, noinline)) static void HideControls(void *context) {
    (void)context;
    [statusLabel removeFromSuperview]; statusLabel = nil;
    [controlCard removeFromSuperview]; controlCard = nil;
}

// These are real interactive system UIButtons, NOT effects with test labels.
// UIKit handles touch tracking, highlight and configuration transitions. They
// have no actions and cannot log in, post, purchase or modify account data.
__attribute__((used, noinline)) static void ShowControls(void *context) {
    (void)context;
    NSArray *windows = [UIApplication sharedApplication].windows;
    UIView *window = nil;
    unsigned budget = 1024;
    for (NSUInteger index = 0; index < windows.count && budget; index++) {
        UIView *candidate = [windows objectAtIndex:index];
        if (installed) RefreshExisting(candidate, 0, &budget);
        if (!window && !candidate.isHidden) window = candidate;
    }
    if (!window) return;
    CGFloat width = window.bounds.size.width - 32;
    if (width < 200) return;
    BOOL reduced = UIAccessibilityIsReduceTransparencyEnabled();
    NSString *message = reduced ? @"控件 E：系统开启了降低透明度" :
        (installed ? [NSString stringWithFormat:@"控件 E：已配置 %lu 个原按钮", configuredCount] :
                     [NSString stringWithFormat:@"控件 E：%@", statusReason]);
    statusLabel = MakeLabel((CGRect){{16, 100}, {width, 60}}, message);
    statusLabel.backgroundColor = [NSClassFromString(@"UIColor") secondarySystemBackgroundColor];
    [window addSubview:statusLabel];
    if (installed && !reduced) {
        controlCard = [[NSClassFromString(@"UIView") alloc] initWithFrame:
            (CGRect){{16, 174}, {width, 204}}];
        controlCard.userInteractionEnabled = YES;
        controlCard.backgroundColor = [NSClassFromString(@"UIColor") secondarySystemBackgroundColor];
        [controlCard addSubview:MakeLabel((CGRect){{0, 0}, {width, 42}}, @"按住按钮，再滑出松开\n观察系统按压与边缘效果")];
        const double colors[4][3] = {{0.15, 0.45, 0.95}, {0.95, 0.35, 0.25},
                                     {0.25, 0.75, 0.45}, {0.95, 0.70, 0.20}};
        for (unsigned index = 0; index < 4; index++) {
            UIView *stripe = [[NSClassFromString(@"UIView") alloc] initWithFrame:
                (CGRect){{width * index / 4, 42}, {width / 4, 162}}];
            stripe.userInteractionEnabled = NO;
            stripe.backgroundColor = [NSClassFromString(@"UIColor") colorWithRed:colors[index][0]
                green:colors[index][1] blue:colors[index][2] alpha:1];
            [controlCard addSubview:stripe];
        }
        for (unsigned index = 0; index < 2; index++) {
            UIButton *button = [buttonClass buttonWithType:1];
            UIButtonConfiguration *configuration = index ?
                [configurationClass prominentGlassButtonConfiguration] : [configurationClass glassButtonConfiguration];
            if (!button || !configuration) continue;
            configuration.title = index ? @"强调玻璃按钮 · 按住" : @"标准玻璃按钮 · 按住";
            configuration.cornerStyle = 4;
            objc_setAssociatedObject(button, &createdKey, [NSNumber numberWithBool:YES], 1);
            button.configuration = configuration;
            button.automaticallyUpdatesConfiguration = YES;
            button.frame = (CGRect){{12, 52 + 76 * index}, {width - 24, 62}};
            button.userInteractionEnabled = YES;
            [controlCard addSubview:button];
        }
        [window addSubview:controlCard];
    }
    dispatch_after_f(dispatch_time(0, 20000000000LL), &_dispatch_main_q, (void *)0, HideControls);
}

static void InstallAndShow(void *context) {
    InstallNativeButtons(context);
    dispatch_after_f(dispatch_time(0, 2000000000LL), &_dispatch_main_q, (void *)0, ShowControls);
}

__attribute__((constructor)) static void StartNativeControls(void) {
    dispatch_async_f(&_dispatch_main_q, (void *)0, InstallAndShow);
}
