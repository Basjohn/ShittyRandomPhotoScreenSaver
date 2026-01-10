"""Performance benchmarks for SRPSS.

This module provides performance benchmarks for key operations:
- Startup time
- Transition FPS
- Memory usage
- Image loading performance

Run with: python -m pytest tests/test_performance.py -v
"""
import pytest
import psutil
import os
from PySide6.QtWidgets import QApplication


@pytest.fixture
def qapp():
    """Create QApplication for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def temp_image_dir(tmp_path):
    """Create temporary directory with test images."""
    img_dir = tmp_path / "images"
    img_dir.mkdir()
    
    # Create a simple test image
    from PySide6.QtGui import QImage, QColor
    img = QImage(800, 600, QImage.Format.Format_RGB32)
    img.fill(QColor(100, 100, 100))
    img.save(str(img_dir / "test1.jpg"))
    img.save(str(img_dir / "test2.jpg"))
    img.save(str(img_dir / "test3.jpg"))
    
    return img_dir


class TestStartupPerformance:
    """Benchmark startup time."""
    
    def test_settings_manager_init_time(self, benchmark):
        """Benchmark SettingsManager initialization time."""
        from core.settings.settings_manager import SettingsManager
        
        def init_settings():
            return SettingsManager(organization="BenchmarkTest", application="Startup")
        
        result = benchmark(init_settings)
        assert result is not None
        
        # Target: < 100ms for settings init
        assert benchmark.stats['mean'] < 0.1, f"Settings init too slow: {benchmark.stats['mean']:.3f}s"
    
    def test_preset_loading_time(self, benchmark, settings_manager):
        """Benchmark preset loading time."""
        from core.presets import apply_preset
        
        def load_preset():
            return apply_preset(settings_manager, "purist")
        
        result = benchmark(load_preset)
        assert result is True
        
        # Target: < 50ms for preset application
        assert benchmark.stats['mean'] < 0.05, f"Preset loading too slow: {benchmark.stats['mean']:.3f}s"


class TestTransitionPerformance:
    """Benchmark transition rendering performance."""
    
    def test_image_load_time(self, benchmark, temp_image_dir):
        """Benchmark image loading time."""
        from PySide6.QtGui import QImage
        
        test_image = temp_image_dir / "test1.jpg"
        
        def load_image():
            return QImage(str(test_image))
        
        result = benchmark(load_image)
        assert not result.isNull()
        
        # Target: < 50ms for 800x600 image
        assert benchmark.stats['mean'] < 0.05, f"Image load too slow: {benchmark.stats['mean']:.3f}s"
    
    def test_image_scaling_time(self, benchmark, temp_image_dir):
        """Benchmark image scaling performance."""
        from PySide6.QtGui import QImage
        from PySide6.QtCore import Qt, QSize
        
        test_image = temp_image_dir / "test1.jpg"
        img = QImage(str(test_image))
        
        def scale_image():
            return img.scaled(
                QSize(1920, 1080),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
        
        result = benchmark(scale_image)
        assert not result.isNull()
        
        # Target: < 100ms for scaling to 1080p
        assert benchmark.stats['mean'] < 0.1, f"Image scaling too slow: {benchmark.stats['mean']:.3f}s"


class TestMemoryUsage:
    """Benchmark memory usage."""
    
    def test_baseline_memory(self, qapp):
        """Measure baseline memory usage."""
        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        
        baseline_mb = mem_info.rss / 1024 / 1024
        
        # Target: < 150MB baseline
        assert baseline_mb < 150, f"Baseline memory too high: {baseline_mb:.1f}MB"
    
    def test_settings_manager_memory(self, settings_manager):
        """Measure SettingsManager memory footprint."""
        process = psutil.Process(os.getpid())
        mem_before = process.memory_info().rss / 1024 / 1024
        
        # Load all settings
        _ = settings_manager.get("widgets", {})
        _ = settings_manager.get("display", {})
        _ = settings_manager.get("transitions", {})
        
        mem_after = process.memory_info().rss / 1024 / 1024
        mem_delta = mem_after - mem_before
        
        # Target: < 10MB for settings
        assert mem_delta < 10, f"Settings memory too high: {mem_delta:.1f}MB"
    
    def test_image_cache_memory(self, temp_image_dir):
        """Measure image cache memory usage."""
        from PySide6.QtGui import QImage
        
        process = psutil.Process(os.getpid())
        mem_before = process.memory_info().rss / 1024 / 1024
        
        # Load 3 images
        images = []
        for i in range(1, 4):
            img = QImage(str(temp_image_dir / f"test{i}.jpg"))
            images.append(img)
        
        mem_after = process.memory_info().rss / 1024 / 1024
        mem_delta = mem_after - mem_before
        
        # Target: < 20MB for 3 images
        assert mem_delta < 20, f"Image cache memory too high: {mem_delta:.1f}MB"


class TestWidgetPerformance:
    """Benchmark widget rendering performance."""
    
    def test_clock_widget_creation(self, benchmark, qapp):
        """Benchmark clock widget creation time."""
        from widgets.clock_widget import ClockWidget
        from PySide6.QtWidgets import QWidget
        
        parent = QWidget()
        
        def create_clock():
            clock = ClockWidget(parent=parent)
            return clock
        
        result = benchmark(create_clock)
        assert result is not None
        
        # Target: < 50ms for widget creation
        assert benchmark.stats['mean'] < 0.05, f"Clock creation too slow: {benchmark.stats['mean']:.3f}s"
        
        parent.deleteLater()
    
    def test_weather_widget_creation(self, benchmark, qapp):
        """Benchmark weather widget creation time."""
        from widgets.weather_widget import WeatherWidget
        from PySide6.QtWidgets import QWidget
        
        parent = QWidget()
        
        def create_weather():
            weather = WeatherWidget(parent=parent)
            return weather
        
        result = benchmark(create_weather)
        assert result is not None
        
        # Target: < 50ms for widget creation
        assert benchmark.stats['mean'] < 0.05, f"Weather creation too slow: {benchmark.stats['mean']:.3f}s"
        
        parent.deleteLater()


class TestValidationPerformance:
    """Benchmark settings validation performance."""
    
    def test_schema_validation_time(self, benchmark):
        """Benchmark settings schema validation."""
        from core.settings.schema import validate_setting
        
        def validate_settings():
            results = []
            results.append(validate_setting("widgets.clock.font_size", 48))
            results.append(validate_setting("display.interval", 10))
            results.append(validate_setting("transitions.duration", 1.5))
            return results
        
        results = benchmark(validate_settings)
        assert all(r[0] for r in results)
        
        # Target: < 10ms for 3 validations
        assert benchmark.stats['mean'] < 0.01, f"Validation too slow: {benchmark.stats['mean']:.3f}s"
    
    def test_schema_repair_time(self, benchmark):
        """Benchmark settings schema repair."""
        from core.settings.schema import repair_setting
        
        def repair_settings():
            results = []
            results.append(repair_setting("widgets.clock.font_size", 5))  # Too small
            results.append(repair_setting("display.interval", 0))  # Invalid
            results.append(repair_setting("transitions.duration", -1))  # Negative
            return results
        
        results = benchmark(repair_settings)
        assert all(r is not None for r in results)
        
        # Target: < 10ms for 3 repairs
        assert benchmark.stats['mean'] < 0.01, f"Repair too slow: {benchmark.stats['mean']:.3f}s"


# Performance targets summary
PERFORMANCE_TARGETS = {
    "startup": {
        "settings_init": "< 100ms",
        "preset_load": "< 50ms",
    },
    "transitions": {
        "image_load": "< 50ms (800x600)",
        "image_scale": "< 100ms (1080p)",
    },
    "memory": {
        "baseline": "< 150MB",
        "settings": "< 10MB delta",
        "image_cache": "< 20MB (3 images)",
    },
    "widgets": {
        "clock_creation": "< 50ms",
        "weather_creation": "< 50ms",
    },
    "validation": {
        "schema_validate": "< 10ms (3 checks)",
        "schema_repair": "< 10ms (3 repairs)",
    },
}


def test_performance_targets_documented():
    """Ensure performance targets are documented."""
    assert PERFORMANCE_TARGETS is not None
    assert len(PERFORMANCE_TARGETS) >= 5
    
    # Verify all categories have targets
    assert "startup" in PERFORMANCE_TARGETS
    assert "transitions" in PERFORMANCE_TARGETS
    assert "memory" in PERFORMANCE_TARGETS
    assert "widgets" in PERFORMANCE_TARGETS
    assert "validation" in PERFORMANCE_TARGETS
