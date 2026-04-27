import py_compile
import sys

files = [
    r'ui/tabs/shared_styles.py',
    r'ui/tabs/widgets_tab_gmail.py',
    r'ui/tabs/widgets_tab.py',
    r'widgets/gmail_widget.py',
]

ok = True
for f in files:
    try:
        py_compile.compile(f, doraise=True)
        print(f'OK: {f}')
    except Exception as e:
        print(f'FAIL: {f} - {e}')
        ok = False

sys.exit(0 if ok else 1)
