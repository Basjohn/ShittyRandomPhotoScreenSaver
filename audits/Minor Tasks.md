1. We need a gate for the visualizer's animation that only allows animation updates if spotify is detected and in playing state. If not we only see the 1 bar floor, this can have sparse polling if you use any polling at all (and force a check when the play/pause controls are clicked, but again, that's only if you decide to use polling)

2. Check our widget positioning system for potential stacking issues and most importantly middle/center positions not applying correctly to items like reddit 2. (But a comprehensive check is ideal)

3. The Setting GUI does a good job of remembering tabs/subsections/scroll points but it never seems to remember which display it opened/closed on and the sizing user applied. It should.

4. Can we make a double left click anywhere on the compositor that doesn't have a widget trigger "Next Image"?

5. Global volume keys are disabled when in the application? (At least in MC mode. I don't want them to interact with the spotify volume but I don't want to block them from working as they normally do)

6. The visualizer doesn't intelligently position itself when using any top positions (top left, center top, top right). In those cases in should (with the same padding) appear underneath the media widget.

It may be best to do 2 & 6 at the same time or at least sequentially so that context is best used.

---------
Long Term, These Require More Planning:

1. Add an item to the context menu that moves the compositor/widgets/etc (everything except the right click menu) while maintaining their z-order heirarchy to the bottom of screen order. Just above the desktop layer. 
The Item can be "On Top / On Bottom" changed when clicked and the active one has a slightly glow to its text or just make the off one grey if you're lazy.

If possible can On Bottom mode (strictly when it is active) detect if the entirety of it is not visible (or like 95%) to the user (covered by other apps) and go into an "Eco Mode" during this period where transitions, and visualiser updates are paused until a degree of visual is regained. This mode should never ever trigger during On Top mode and should recover extensively when focus or visuals are restored.