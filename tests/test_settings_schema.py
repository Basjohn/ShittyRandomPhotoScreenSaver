"""
Tests for settings schema and validation.
"""
from core.settings.schema import (
    SettingType,
    SettingDefinition,
    validate_setting,
    repair_setting,
    validate_settings_dict,
    repair_settings_dict,
    get_default_value,
    get_setting_description,
    SETTINGS_SCHEMA
)


class TestSettingDefinition:
    """Test SettingDefinition class."""
    
    def test_bool_validation(self):
        """Test boolean setting validation."""
        setting = SettingDefinition(SettingType.BOOL, default=True)
        
        assert setting.validate(True)[0] is True
        assert setting.validate(False)[0] is True
        assert setting.validate("true")[0] is False
        assert setting.validate(1)[0] is False
    
    def test_int_validation(self):
        """Test integer setting validation."""
        setting = SettingDefinition(SettingType.INT, default=10, min_value=0, max_value=100)
        
        assert setting.validate(50)[0] is True
        assert setting.validate(0)[0] is True
        assert setting.validate(100)[0] is True
        assert setting.validate(-1)[0] is False
        assert setting.validate(101)[0] is False
        assert setting.validate("50")[0] is False
    
    def test_string_validation_with_allowed_values(self):
        """Test string validation with allowed values."""
        setting = SettingDefinition(
            SettingType.STRING,
            default="option1",
            allowed_values=["option1", "option2", "option3"]
        )
        
        assert setting.validate("option1")[0] is True
        assert setting.validate("option2")[0] is True
        assert setting.validate("invalid")[0] is False
    
    def test_float_validation(self):
        """Test float setting validation."""
        setting = SettingDefinition(SettingType.FLOAT, default=1.0, min_value=0.0, max_value=10.0)
        
        assert setting.validate(5.5)[0] is True
        assert setting.validate(5)[0] is True  # int is acceptable for float
        assert setting.validate(-0.1)[0] is False
        assert setting.validate(10.1)[0] is False


class TestSettingRepair:
    """Test setting repair functionality."""
    
    def test_bool_repair_from_string(self):
        """Test repairing bool from string."""
        setting = SettingDefinition(SettingType.BOOL, default=False)
        
        assert setting.repair("true") is True
        assert setting.repair("1") is True
        assert setting.repair("yes") is True
        assert setting.repair("false") is False
        assert setting.repair("0") is False
    
    def test_int_repair_clamp(self):
        """Test repairing int by clamping to range."""
        setting = SettingDefinition(SettingType.INT, default=50, min_value=0, max_value=100)
        
        assert setting.repair(-10) == 0
        assert setting.repair(150) == 100
        assert setting.repair(50) == 50
    
    def test_string_repair_to_allowed_value(self):
        """Test repairing string to first allowed value."""
        setting = SettingDefinition(
            SettingType.STRING,
            default="option1",
            allowed_values=["option1", "option2", "option3"]
        )
        
        assert setting.repair("invalid") == "option1"
        assert setting.repair("option2") == "option2"
    
    def test_repair_falls_back_to_default(self):
        """Test that repair falls back to default when unrepairable."""
        setting = SettingDefinition(SettingType.INT, default=10)
        
        # Can't convert dict to int, should return default
        assert setting.repair({"key": "value"}) == 10


class TestValidateSetting:
    """Test validate_setting function."""
    
    def test_validate_known_setting(self):
        """Test validating a known setting."""
        is_valid, error = validate_setting("widgets.clock.enabled", True)
        assert is_valid is True
        assert error is None
        
        is_valid, error = validate_setting("widgets.clock.enabled", "not a bool")
        assert is_valid is False
        assert error is not None
    
    def test_validate_unknown_setting(self):
        """Test validating an unknown setting (should allow)."""
        is_valid, error = validate_setting("unknown.setting", "any value")
        assert is_valid is True
        assert error is None
    
    def test_validate_font_size_range(self):
        """Test validating font size within range."""
        is_valid, _ = validate_setting("widgets.clock.font_size", 48)
        assert is_valid is True
        
        is_valid, _ = validate_setting("widgets.clock.font_size", 5)
        assert is_valid is False
        
        is_valid, _ = validate_setting("widgets.clock.font_size", 250)
        assert is_valid is False


class TestRepairSetting:
    """Test repair_setting function."""
    
    def test_repair_out_of_range_font_size(self):
        """Test repairing out-of-range font size."""
        repaired = repair_setting("widgets.clock.font_size", 5)
        assert repaired == 12  # min_value
        
        repaired = repair_setting("widgets.clock.font_size", 250)
        assert repaired == 200  # max_value
    
    def test_repair_invalid_position(self):
        """Test repairing invalid position."""
        repaired = repair_setting("widgets.clock.position", "Invalid Position")
        assert repaired == "Top Left"  # First allowed value
    
    def test_repair_unknown_setting(self):
        """Test repairing unknown setting (should return as-is)."""
        repaired = repair_setting("unknown.setting", "value")
        assert repaired == "value"


class TestValidateSettingsDict:
    """Test validate_settings_dict function."""
    
    def test_validate_valid_dict(self):
        """Test validating a valid settings dictionary."""
        settings = {
            "widgets.clock.enabled": True,
            "widgets.clock.font_size": 48,
            "widgets.clock.position": "Top Right"
        }
        
        all_valid, errors = validate_settings_dict(settings)
        assert all_valid is True
        assert len(errors) == 0
    
    def test_validate_invalid_dict(self):
        """Test validating an invalid settings dictionary."""
        settings = {
            "widgets.clock.enabled": "not a bool",
            "widgets.clock.font_size": 5,  # Below minimum
            "widgets.clock.position": "Invalid"
        }
        
        all_valid, errors = validate_settings_dict(settings)
        assert all_valid is False
        assert len(errors) == 3


class TestRepairSettingsDict:
    """Test repair_settings_dict function."""
    
    def test_repair_multiple_settings(self):
        """Test repairing multiple invalid settings."""
        settings = {
            "widgets.clock.enabled": "true",  # String instead of bool
            "widgets.clock.font_size": 5,  # Below minimum
            "widgets.clock.position": "Invalid"  # Not in allowed values
        }
        
        repaired = repair_settings_dict(settings)
        
        assert repaired["widgets.clock.enabled"] is True
        assert repaired["widgets.clock.font_size"] == 12
        assert repaired["widgets.clock.position"] == "Top Left"
    
    def test_repair_preserves_valid_settings(self):
        """Test that repair preserves valid settings."""
        settings = {
            "widgets.clock.enabled": True,
            "widgets.clock.font_size": 48
        }
        
        repaired = repair_settings_dict(settings)
        
        assert repaired == settings


class TestGetDefaultValue:
    """Test get_default_value function."""
    
    def test_get_known_default(self):
        """Test getting default for known setting."""
        default = get_default_value("widgets.clock.enabled")
        assert default is True
        
        default = get_default_value("widgets.clock.font_size")
        assert default == 48
    
    def test_get_unknown_default(self):
        """Test getting default for unknown setting."""
        default = get_default_value("unknown.setting")
        assert default is None


class TestGetSettingDescription:
    """Test get_setting_description function."""
    
    def test_get_known_description(self):
        """Test getting description for known setting."""
        desc = get_setting_description("widgets.clock.enabled")
        assert "clock" in desc.lower()
        assert len(desc) > 0
    
    def test_get_unknown_description(self):
        """Test getting description for unknown setting."""
        desc = get_setting_description("unknown.setting")
        assert desc == ""


class TestSettingsSchema:
    """Test SETTINGS_SCHEMA completeness."""
    
    def test_schema_has_common_settings(self):
        """Test that schema includes common settings."""
        required_keys = [
            "display.interval",
            "display.transition_duration",
            "widgets.clock.enabled",
            "widgets.weather.enabled",
            "widgets.media.enabled",
            "preset"
        ]
        
        for key in required_keys:
            assert key in SETTINGS_SCHEMA, f"Missing required setting: {key}"
    
    def test_all_definitions_have_defaults(self):
        """Test that all setting definitions have defaults."""
        for key, definition in SETTINGS_SCHEMA.items():
            assert definition.default is not None or definition.setting_type == SettingType.DICT, \
                f"Setting {key} missing default value"
    
    def test_position_settings_have_valid_allowed_values(self):
        """Test that position settings have correct allowed values."""
        position_keys = [
            "widgets.clock.position",
            "widgets.weather.position",
            "widgets.media.position"
        ]
        
        expected_positions = [
            "Top Left", "Top Center", "Top Right",
            "Middle Left", "Center", "Middle Right",
            "Bottom Left", "Bottom Center", "Bottom Right"
        ]
        
        for key in position_keys:
            if key in SETTINGS_SCHEMA:
                definition = SETTINGS_SCHEMA[key]
                assert definition.allowed_values == expected_positions, \
                    f"Setting {key} has incorrect allowed values"


class TestIntegrationWithSettingsManager:
    """Test integration scenarios with SettingsManager."""
    
    def test_validate_and_repair_workflow(self):
        """Test typical validate-then-repair workflow."""
        # Simulate loading corrupted settings
        loaded_settings = {
            "widgets.clock.font_size": "48",  # String instead of int
            "display.interval": -5,  # Below minimum
            "widgets.clock.position": "Invalid Position"
        }
        
        # Validate
        all_valid, errors = validate_settings_dict(loaded_settings)
        assert all_valid is False
        
        # Repair
        repaired = repair_settings_dict(loaded_settings)
        
        # Validate repaired
        all_valid, errors = validate_settings_dict(repaired)
        assert all_valid is True
        
        # Check specific repairs
        assert repaired["widgets.clock.font_size"] == 48
        assert repaired["display.interval"] == 5
        assert repaired["widgets.clock.position"] in SETTINGS_SCHEMA["widgets.clock.position"].allowed_values
