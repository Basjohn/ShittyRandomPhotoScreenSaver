"""Quick test to verify QGraphicsOpacityEffect works on QLabel."""
from PySide6.QtWidgets import QApplication, QLabel, QGraphicsOpacityEffect, QWidget
from PySide6.QtGui import QPixmap, QColor
from PySide6.QtCore import QTimer, Qt
import sys

app = QApplication(sys.argv)

# Create parent widget
parent = QWidget()
parent.resize(600, 400)
parent.setStyleSheet("background: black;")

# Create two labels - one behind, one in front with opacity
label_old = QLabel(parent)
label_old.setGeometry(0, 0, 600, 400)
label_old.setStyleSheet("background: red;")
label_old.setAlignment(Qt.AlignmentFlag.AlignCenter)
label_old.setText("OLD IMAGE")
label_old.show()

label_new = QLabel(parent)
label_new.setGeometry(0, 0, 600, 400)
label_new.setStyleSheet("background: blue;")
label_new.setAlignment(Qt.AlignmentFlag.AlignCenter)
label_new.setText("NEW IMAGE")

# Apply opacity effect
effect = QGraphicsOpacityEffect()
effect.setOpacity(0.0)
label_new.setGraphicsEffect(effect)
label_new.show()

print(f"Effect created: {effect is not None}")
print(f"Effect opacity: {effect.opacity()}")
print(f"Label has effect: {label_new.graphicsEffect() is not None}")

# Animate opacity
current_opacity = [0.0]
def update_opacity():
    current_opacity[0] += 0.1
    if current_opacity[0] > 1.0:
        current_opacity[0] = 1.0
        timer.stop()
        print("Animation complete")
    effect.setOpacity(current_opacity[0])
    print(f"Opacity now: {current_opacity[0]}")

timer = QTimer()
timer.timeout.connect(update_opacity)
timer.start(100)

parent.show()

# Auto-quit after 2 seconds
QTimer.singleShot(2000, app.quit)

sys.exit(app.exec())
