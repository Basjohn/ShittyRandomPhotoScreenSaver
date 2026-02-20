"""
Transition Factory - Extracted from DisplayWidget for better separation.

Handles transition type selection, direction randomization, and instantiation
based on settings and hardware capabilities.
"""
from __future__ import annotations

import random
from typing import Optional, TYPE_CHECKING, Callable

from core.logging.logger import get_logger, is_perf_metrics_enabled
from core.settings.defaults import get_default_settings
from core.settings.settings_manager import SettingsManager
from core.resources.manager import ResourceManager
from core.process import ProcessSupervisor, WorkerType, MessageType

# Transition imports
from transitions.base_transition import BaseTransition
from transitions.crossfade_transition import CrossfadeTransition
from transitions.slide_transition import SlideTransition, SlideDirection
from transitions.wipe_transition import WipeTransition, WipeDirection
from transitions.diffuse_transition import DiffuseTransition
from transitions.block_puzzle_flip_transition import BlockPuzzleFlipTransition

# GL Compositor transitions
from transitions.gl_compositor_crossfade_transition import GLCompositorCrossfadeTransition
from transitions.gl_compositor_slide_transition import GLCompositorSlideTransition
from transitions.gl_compositor_wipe_transition import GLCompositorWipeTransition
from transitions.gl_compositor_diffuse_transition import GLCompositorDiffuseTransition
from transitions.gl_compositor_peel_transition import GLCompositorPeelTransition
from transitions.gl_compositor_blockspin_transition import GLCompositorBlockSpinTransition
from transitions.gl_compositor_blockflip_transition import GLCompositorBlockFlipTransition
from transitions.gl_compositor_blinds_transition import GLCompositorBlindsTransition
from transitions.gl_compositor_raindrops_transition import GLCompositorRainDropsTransition
from transitions.gl_compositor_warp_transition import GLCompositorWarpTransition
from transitions.gl_compositor_crumble_transition import GLCompositorCrumbleTransition
from transitions.gl_compositor_particle_transition import GLCompositorParticleTransition
from transitions.gl_compositor_burn_transition import GLCompositorBurnTransition

if TYPE_CHECKING:
    pass  # Future type hints if needed

logger = get_logger(__name__)


# Direction maps used across multiple transition types
SLIDE_DIRECTION_MAP = {
    'Left to Right': SlideDirection.LEFT,
    'Right to Left': SlideDirection.RIGHT,
    'Top to Bottom': SlideDirection.DOWN,
    'Bottom to Top': SlideDirection.UP,
    'Diagonal TL-BR': SlideDirection.DIAG_TL_BR,
    'Diagonal TR-BL': SlideDirection.DIAG_TR_BL,
    'Diagonal TL to BR': SlideDirection.DIAG_TL_BR,
    'Diagonal TR to BL': SlideDirection.DIAG_TR_BL,
}

SLIDE_DIRECTION_REVERSE = {v: k for k, v in SLIDE_DIRECTION_MAP.items()}

WIPE_DIRECTION_MAP = {
    'Left to Right': WipeDirection.LEFT_TO_RIGHT,
    'Right to Left': WipeDirection.RIGHT_TO_LEFT,
    'Top to Bottom': WipeDirection.TOP_TO_BOTTOM,
    'Bottom to Top': WipeDirection.BOTTOM_TO_TOP,
    'Diagonal TL-BR': WipeDirection.DIAG_TL_BR,
    'Diagonal TR-BL': WipeDirection.DIAG_TR_BL,
}

ALL_SLIDE_DIRECTIONS = [
    SlideDirection.LEFT,
    SlideDirection.RIGHT,
    SlideDirection.UP,
    SlideDirection.DOWN,
]

ALL_BLOCKSPIN_DIRECTIONS = [
    SlideDirection.LEFT,
    SlideDirection.RIGHT,
    SlideDirection.UP,
    SlideDirection.DOWN,
    SlideDirection.DIAG_TL_BR,
    SlideDirection.DIAG_TR_BL,
]


class TransitionFactory:
    """Factory for creating transition instances based on settings.
    
    Extracted from DisplayWidget to reduce file size and improve testability.
    """
    
    def __init__(
        self,
        settings_manager: SettingsManager,
        resource_manager: Optional[ResourceManager] = None,
        compositor_checker: Optional[Callable[[], bool]] = None,
        compositor_ensurer: Optional[Callable[[], None]] = None,
    ):
        """Initialize the factory.
        
        Args:
            settings_manager: Settings manager for reading transition config
            resource_manager: Resource manager for transition lifecycle
            compositor_checker: Callable that returns True if GL compositor is available
            compositor_ensurer: Callable that ensures GL compositor is initialized
        """
        self._settings = settings_manager
        self._resources = resource_manager
        self._check_compositor = compositor_checker or (lambda: False)
        self._ensure_compositor = compositor_ensurer or (lambda: None)
        
        # ProcessSupervisor for TransitionWorker integration
        self._process_supervisor: Optional[ProcessSupervisor] = None
        self._precompute_cache: dict = {}  # Cache precomputed transition data
    
    def set_process_supervisor(self, supervisor: Optional[ProcessSupervisor]) -> None:
        """Set the ProcessSupervisor for TransitionWorker integration.
        
        When set and TransitionWorker is running, transition precomputation
        is offloaded to a separate process for better startup performance.
        """
        self._process_supervisor = supervisor
        if supervisor is not None:
            try:
                if supervisor.is_running(WorkerType.TRANSITION):
                    logger.info("[TRANSITION_FACTORY] TransitionWorker available for precomputation")
            except Exception as e:
                logger.debug("[TRANSITION_FACTORY] Exception suppressed: %s", e)
    
    def _precompute_via_worker(
        self,
        transition_type: str,
        width: int = 1920,
        height: int = 1080,
        params: Optional[dict] = None,
        timeout_ms: int = 100,
    ) -> Optional[dict]:
        """Precompute transition data using TransitionWorker.
        
        Returns precomputed data if successful, None if worker unavailable or failed.
        """
        if not self._process_supervisor:
            return None
        
        try:
            if not self._process_supervisor.is_running(WorkerType.TRANSITION):
                return None
            
            import time
            
            payload = {
                "transition_type": transition_type,
                "params": {
                    "screen_width": width,
                    "screen_height": height,
                    **(params or {}),
                },
                "use_cache": True,
            }
            
            correlation_id = self._process_supervisor.send_message(
                WorkerType.TRANSITION,
                MessageType.TRANSITION_PRECOMPUTE,
                payload=payload,
            )
            
            if not correlation_id:
                return None
            
            # Poll for response with short timeout
            start_time = time.time()
            timeout_s = timeout_ms / 1000.0
            
            while (time.time() - start_time) < timeout_s:
                responses = self._process_supervisor.poll_responses(WorkerType.TRANSITION, max_count=5)
                
                for response in responses:
                    if response.correlation_id == correlation_id:
                        if response.success:
                            data = response.payload.get("data", {})
                            if is_perf_metrics_enabled():
                                proc_time = response.processing_time_ms or 0
                                cached = response.payload.get("cached", False)
                                logger.info(
                                    "[PERF] [WORKER] TransitionWorker precompute: %s in %.1fms (cached=%s)",
                                    transition_type, proc_time, cached
                                )
                            return data
                        else:
                            return None
                
                time.sleep(0.005)
            
            return None
            
        except Exception as e:
            logger.debug("[TRANSITION_FACTORY] TransitionWorker precompute error: %s", e)
            return None
    
    def create_transition(self) -> Optional[BaseTransition]:
        """Create the next transition based on current settings.
        
        Returns:
            Configured transition instance, or None on error
        """
        try:
            return self._create_transition_impl()
        except Exception as exc:
            logger.error("Failed to create transition: %s", exc, exc_info=True)
            return None
    
    def _create_transition_impl(self) -> Optional[BaseTransition]:
        """Internal implementation of transition creation."""
        transitions_settings = self._settings.get('transitions', {})
        if not isinstance(transitions_settings, dict):
            transitions_settings = {}

        canonical_transitions = get_default_settings().get('transitions', {})
        if not isinstance(canonical_transitions, dict):
            canonical_transitions = {}
        
        # Get transition type
        transition_type = transitions_settings.get('type') or canonical_transitions.get('type') or 'Crossfade'
        requested_type = transition_type
        
        # Handle random mode
        random_mode, random_choice_value = self._get_random_mode(
            transitions_settings, transition_type,
        )
        if random_mode and random_choice_value:
            transition_type = random_choice_value
        
        # Get duration
        duration_ms = self._get_duration(transitions_settings, transition_type)
        
        # Get easing and hw_accel
        easing_str = transitions_settings.get('easing') or 'Auto'
        hw_accel = self._get_hw_accel()
        
        # Create the appropriate transition
        transition = self._create_by_type(
            transition_type, transitions_settings, duration_ms, easing_str, hw_accel
        )
        
        if transition:
            transition.set_resource_manager(self._resources)
            self._log_selection(requested_type, transition_type, random_mode, random_choice_value)
        
        return transition
    
    # Concrete transition names the factory can instantiate directly.
    _CONCRETE_TYPES = frozenset({
        'Crossfade', 'Slide', 'Wipe', 'Peel', 'Shuffle', 'Claw Marks',
        'Warp Dissolve', 'Diffuse', 'Rain Drops', 'Ripple',
        'Block Puzzle Flip', '3D Block Spins', 'Blinds', 'Crumble', 'Particle', 'Burn',
    })

    def _get_random_mode(
        self, settings: dict, transition_type: str,
    ) -> tuple[bool, Optional[str]]:
        """Get random mode state and choice.

        Random mode is active when *either*:
        - ``random_always`` is True in the transitions settings, **or**
        - ``transition_type`` is literally ``"Random"`` (the canonical default
          and the value stored when the user picks *Random* from the context
          menu).

        When random mode is active we first try to read a pre-resolved
        ``transitions.random_choice`` (set by the engine before each
        rotation).  If that key is missing we fall back to picking a
        concrete type ourselves so the factory never passes the bare
        string ``"Random"`` into ``_create_by_type``.
        """
        try:
            rnd = settings.get('random_always', False)
            rnd = SettingsManager.to_bool(rnd, False)
            random_mode = bool(rnd) or transition_type == 'Random'
            random_choice_value = None
            if random_mode:
                chosen = self._settings.get('transitions.random_choice', None)
                if isinstance(chosen, str) and chosen and chosen != 'Random':
                    random_choice_value = chosen
                else:
                    # Engine didn't pre-resolve a choice — pick one now.
                    random_choice_value = self._pick_random_transition(settings)
            return random_mode, random_choice_value
        except Exception as e:
            logger.debug("[TRANSITION_FACTORY] Exception suppressed: %s", e)
            return False, None

    def _pick_random_transition(self, settings: dict) -> str:
        """Pick a concrete random transition type (factory-side fallback)."""
        try:
            hw = SettingsManager.to_bool(
                self._settings.get('display.hw_accel', True), True,
            )
            base = ['Crossfade', 'Slide', 'Wipe', 'Diffuse', 'Block Puzzle Flip']
            gl_only = [
                'Blinds', 'Peel', '3D Block Spins', 'Ripple',
                'Warp Dissolve', 'Crumble', 'Particle', 'Burn',
            ]
            pool_cfg = (
                settings.get('pool', {})
                if isinstance(settings.get('pool', {}), dict)
                else {}
            )

            def _in_pool(name: str) -> bool:
                if name == 'Ripple':
                    raw = pool_cfg.get('Ripple', pool_cfg.get('Rain Drops', True))
                else:
                    raw = pool_cfg.get(name, True)
                return bool(SettingsManager.to_bool(raw, True))

            available = [n for n in base if _in_pool(n)]
            if hw:
                available.extend(n for n in gl_only if _in_pool(n))
            if not available:
                available = ['Crossfade']

            last = self._settings.get('transitions.last_random_choice', None)
            candidates = [t for t in available if t != last] or available
            return random.choice(candidates)
        except Exception as e:
            logger.debug("[TRANSITION_FACTORY] _pick_random_transition error: %s", e)
            return 'Crossfade'
    
    def _get_duration(self, settings: dict, transition_type: str) -> int:
        """Get duration for the transition type."""
        canonical_transitions = get_default_settings().get('transitions', {})
        if not isinstance(canonical_transitions, dict):
            canonical_transitions = {}

        base_duration_raw = settings.get('duration_ms', canonical_transitions.get('duration_ms', 1300))
        try:
            base_duration_ms = int(base_duration_raw)
        except Exception as e:
            logger.debug("[TRANSITION_FACTORY] Exception suppressed: %s", e)
            base_duration_ms = 1300
        
        duration_ms = base_duration_ms
        try:
            durations_cfg = settings.get('durations', {})
            canonical_durations = canonical_transitions.get('durations', {})
            if not isinstance(canonical_durations, dict):
                canonical_durations = {}

            if isinstance(durations_cfg, dict):
                per_type_raw = durations_cfg.get(transition_type)
            else:
                per_type_raw = None

            if per_type_raw is None:
                per_type_raw = canonical_durations.get(transition_type)

            if per_type_raw is not None:
                duration_ms = int(per_type_raw)
        except Exception as e:
            logger.debug("[TRANSITION_FACTORY] Exception suppressed: %s", e)
        
        return duration_ms
    
    def _get_hw_accel(self) -> bool:
        """Check if hardware acceleration is enabled."""
        try:
            hw_raw = self._settings.get('display.hw_accel', True)
        except Exception as e:
            logger.debug("[TRANSITION_FACTORY] Exception suppressed: %s", e)
            hw_raw = True
        return SettingsManager.to_bool(hw_raw, True)
    
    def _use_compositor(self, hw_accel: bool) -> bool:
        """Check if compositor should be used."""
        if not hw_accel:
            return False
        try:
            self._ensure_compositor()
        except Exception:
            logger.debug("[GL COMPOSITOR] Failed to ensure compositor", exc_info=True)
        return self._check_compositor()
    
    def _create_by_type(
        self,
        transition_type: str,
        settings: dict,
        duration_ms: int,
        easing_str: str,
        hw_accel: bool,
    ) -> Optional[BaseTransition]:
        """Create transition by type name."""
        use_compositor = self._use_compositor(hw_accel)
        
        if transition_type == 'Crossfade':
            return self._create_crossfade(duration_ms, easing_str, use_compositor)
        
        if transition_type == 'Slide':
            return self._create_slide(settings, duration_ms, easing_str, use_compositor)
        
        if transition_type == 'Wipe':
            return self._create_wipe(settings, duration_ms, easing_str, use_compositor)
        
        if transition_type == 'Peel':
            return self._create_peel(settings, duration_ms, easing_str, use_compositor)
        
        if transition_type in ('Shuffle', 'Claw Marks'):
            # Retired transitions map to Crossfade
            return CrossfadeTransition(duration_ms, easing_str)
        
        if transition_type == 'Warp Dissolve':
            return self._create_warp(duration_ms, easing_str, use_compositor)
        
        if transition_type == 'Diffuse':
            return self._create_diffuse(settings, duration_ms, easing_str, use_compositor)
        
        if transition_type in ('Rain Drops', 'Ripple'):
            return self._create_raindrops(settings, duration_ms, easing_str, use_compositor)
        
        if transition_type == 'Block Puzzle Flip':
            return self._create_blockflip(settings, duration_ms, use_compositor)
        
        if transition_type == '3D Block Spins':
            return self._create_blockspin(settings, duration_ms, easing_str, use_compositor)
        
        if transition_type == 'Blinds':
            return self._create_blinds(settings, duration_ms, use_compositor)
        
        if transition_type == 'Crumble':
            return self._create_crumble(settings, duration_ms, use_compositor)
        
        if transition_type == 'Particle':
            return self._create_particle(settings, duration_ms, use_compositor)
        
        if transition_type == 'Burn':
            return self._create_burn(settings, duration_ms, easing_str, use_compositor)
        
        # Unknown type - fallback to Crossfade (use same path as normal creation)
        logger.warning("Unknown transition type: %s, using Crossfade", transition_type)
        return self._create_crossfade(duration_ms, easing_str, use_compositor)
    
    # Individual transition creators
    
    def _create_crossfade(self, duration_ms: int, easing_str: str, use_compositor: bool) -> BaseTransition:
        if use_compositor:
            return GLCompositorCrossfadeTransition(duration_ms, easing_str)
        return CrossfadeTransition(duration_ms, easing_str)
    
    def _create_slide(self, settings: dict, duration_ms: int, easing_str: str, use_compositor: bool) -> BaseTransition:
        slide_settings = settings.get('slide', {}) if isinstance(settings.get('slide', {}), dict) else {}
        direction = self._get_slide_direction(settings, slide_settings, 'slide')
        
        if use_compositor:
            return GLCompositorSlideTransition(duration_ms, direction, easing_str)
        return SlideTransition(duration_ms, direction, easing_str)
    
    def _create_wipe(self, settings: dict, duration_ms: int, easing_str: str, use_compositor: bool) -> BaseTransition:
        wipe_settings = settings.get('wipe', {}) if isinstance(settings.get('wipe', {}), dict) else {}
        direction = self._get_wipe_direction(settings, wipe_settings)
        
        if use_compositor:
            return GLCompositorWipeTransition(duration_ms, direction, easing_str)
        return WipeTransition(duration_ms, direction, easing_str)
    
    def _create_peel(self, settings: dict, duration_ms: int, easing_str: str, use_compositor: bool) -> BaseTransition:
        peel_settings = settings.get('peel', {}) if isinstance(settings.get('peel', {}), dict) else {}
        direction = self._get_slide_direction(settings, peel_settings, 'peel')
        strips = 12
        
        if use_compositor:
            return GLCompositorPeelTransition(duration_ms, direction, strips, easing_str)
        return CrossfadeTransition(duration_ms, easing_str)  # CPU fallback
    
    def _create_warp(self, duration_ms: int, easing_str: str, use_compositor: bool) -> BaseTransition:
        if use_compositor:
            return GLCompositorWarpTransition(duration_ms, easing_str)
        return CrossfadeTransition(duration_ms, easing_str)
    
    def _create_diffuse(self, settings: dict, duration_ms: int, easing_str: str, use_compositor: bool) -> BaseTransition:
        diffuse_settings = settings.get('diffuse', {}) if isinstance(settings.get('diffuse', {}), dict) else {}
        block_size = self._safe_int(diffuse_settings.get('block_size', 50), 50)
        shape = diffuse_settings.get('shape', 'Rectangle') or 'Rectangle'
        
        if use_compositor:
            return GLCompositorDiffuseTransition(duration_ms, block_size, shape, easing_str)
        return DiffuseTransition(duration_ms, block_size, shape)
    
    def _create_raindrops(self, settings: dict, duration_ms: int, easing_str: str, use_compositor: bool) -> BaseTransition:
        ripple_settings = settings.get('ripple', {}) if isinstance(settings.get('ripple', {}), dict) else {}
        ripple_count = self._safe_int(ripple_settings.get('ripple_count', 3), 3)
        if use_compositor:
            return GLCompositorRainDropsTransition(duration_ms, easing_str, ripple_count)
        return CrossfadeTransition(duration_ms, easing_str)
    
    def _create_blockflip(self, settings: dict, duration_ms: int, use_compositor: bool) -> BaseTransition:
        block_flip_settings = settings.get('block_flip', {}) if isinstance(settings.get('block_flip', {}), dict) else {}
        rows = self._safe_int(block_flip_settings.get('rows', 4), 4)
        cols = self._safe_int(block_flip_settings.get('cols', 6), 6)
        
        dir_str = block_flip_settings.get('direction', 'Random') or 'Random'
        if dir_str == 'Random':
            all_dirs = [
                SlideDirection.LEFT, SlideDirection.RIGHT,
                SlideDirection.UP, SlideDirection.DOWN,
                SlideDirection.DIAG_TL_BR, SlideDirection.DIAG_TR_BL,
            ]
            direction = random.choice(all_dirs)
        else:
            direction = SLIDE_DIRECTION_MAP.get(dir_str, SlideDirection.LEFT)
        
        if use_compositor:
            return GLCompositorBlockFlipTransition(duration_ms, rows, cols, flip_duration_ms=500, direction=direction)
        return BlockPuzzleFlipTransition(duration_ms, rows, cols, flip_duration_ms=500, direction=direction)
    
    def _create_blockspin(self, settings: dict, duration_ms: int, easing_str: str, use_compositor: bool) -> BaseTransition:
        blockspin_settings = settings.get('blockspin', {}) if isinstance(settings.get('blockspin', {}), dict) else {}
        dir_str = blockspin_settings.get('direction', 'Random') or 'Random'
        
        if dir_str == 'Random':
            direction = random.choice(ALL_BLOCKSPIN_DIRECTIONS)
        else:
            direction = SLIDE_DIRECTION_MAP.get(dir_str, SlideDirection.LEFT)
        
        if use_compositor:
            return GLCompositorBlockSpinTransition(duration_ms, easing_str, direction)
        return CrossfadeTransition(duration_ms, easing_str)
    
    def _create_blinds(self, settings: dict, duration_ms: int, use_compositor: bool) -> BaseTransition:
        if use_compositor:
            blinds_cfg = settings.get('blinds', {})
            if not isinstance(blinds_cfg, dict):
                blinds_cfg = {}
            feather = float(blinds_cfg.get('feather', 2)) / 25.0  # slider 0-25 → 0.0-1.0 → shader 0.0-0.5
            feather = max(0.001, min(0.5, feather * 0.5))
            direction_str = str(blinds_cfg.get('direction', 'Horizontal'))
            if direction_str == 'Random':
                direction_str = random.choice(['Horizontal', 'Vertical', 'Diagonal'])
            direction_map = {'Horizontal': 0, 'Vertical': 1, 'Diagonal': 2}
            direction = direction_map.get(direction_str, 0)
            return GLCompositorBlindsTransition(
                duration_ms=duration_ms,
                feather=feather,
                direction=direction,
            )
        return CrossfadeTransition(duration_ms)
    
    def _create_crumble(self, settings: dict, duration_ms: int, use_compositor: bool) -> BaseTransition:
        # Get canonical defaults from defaults.py
        from core.settings.defaults import get_default_settings
        canonical = get_default_settings().get('transitions', {}).get('crumble', {})
        
        crumble_settings = settings.get('crumble', {}) if isinstance(settings.get('crumble', {}), dict) else {}
        piece_count = self._safe_int(crumble_settings.get('piece_count', canonical.get('piece_count', 14)), 14)
        crack_complexity = self._safe_float(crumble_settings.get('crack_complexity', canonical.get('crack_complexity', 1.0)), 1.0)
        weight_str = crumble_settings.get('weighting', canonical.get('weighting', 'Random Choice'))
        weight_map = {
            'Top Weighted': 0.0,
            'Bottom Weighted': 1.0,
            'Random Weighted': 2.0,
            'Random Choice': 3.0,
            'Age Weighted': 4.0,
        }
        weight_mode = weight_map.get(weight_str, 0.0)
        
        if use_compositor:
            return GLCompositorCrumbleTransition(duration_ms, piece_count, crack_complexity, False, weight_mode)
        return CrossfadeTransition(duration_ms)
    
    def _create_burn(self, settings: dict, duration_ms: int, easing_str: str, use_compositor: bool) -> BaseTransition:
        burn_cfg = settings.get('burn', {})
        if not isinstance(burn_cfg, dict):
            burn_cfg = {}
        dir_str = burn_cfg.get('direction', 'Random') or 'Random'
        dir_map = {
            'Left to Right': 0, 'Right to Left': 1,
            'Top to Bottom': 2, 'Bottom to Top': 3, 'Center Out': 4,
        }
        if dir_str == 'Random':
            direction = random.randint(0, 4)
        else:
            direction = dir_map.get(dir_str, 0)
        jaggedness = self._safe_float(burn_cfg.get('jaggedness', 0.5), 0.5)
        glow_intensity = self._safe_float(burn_cfg.get('glow_intensity', 0.7), 0.7)
        char_width = self._safe_float(burn_cfg.get('char_width', 0.5), 0.5)
        smoke_enabled = SettingsManager.to_bool(burn_cfg.get('smoke_enabled', True), True)
        smoke_density = self._safe_float(burn_cfg.get('smoke_density', 0.5), 0.5)
        ash_enabled = SettingsManager.to_bool(burn_cfg.get('ash_enabled', True), True)
        ash_density = self._safe_float(burn_cfg.get('ash_density', 0.5), 0.5)
        if use_compositor:
            return GLCompositorBurnTransition(
                duration_ms=duration_ms,
                direction=direction,
                jaggedness=jaggedness,
                glow_intensity=glow_intensity,
                char_width=char_width,
                smoke_enabled=smoke_enabled,
                smoke_density=smoke_density,
                ash_enabled=ash_enabled,
                ash_density=ash_density,
                easing=easing_str,
            )
        return CrossfadeTransition(duration_ms, easing_str)

    def _create_particle(self, settings: dict, duration_ms: int, use_compositor: bool) -> BaseTransition:
        # Get canonical defaults from defaults.py
        from core.settings.defaults import get_default_settings
        canonical = get_default_settings().get('transitions', {}).get('particle', {})
        
        particle_settings = settings.get('particle', {}) if isinstance(settings.get('particle', {}), dict) else {}
        
        mode_str = particle_settings.get('mode', canonical.get('mode', 'Converge'))
        mode_map = {
            'Directional': 0,
            'Swirl': 1,
            'Converge': 2,  # Particles converge from all edges to center
            'Random': 3,
        }
        mode = mode_map.get(mode_str, 0)
        
        direction_str = particle_settings.get('direction', canonical.get('direction', 'Left to Right'))
        direction_map = {
            'Left to Right': 0,
            'Right to Left': 1,
            'Top to Bottom': 2,
            'Bottom to Top': 3,
            'Top-Left to Bottom-Right': 4,
            'Top-Right to Bottom-Left': 5,
            'Bottom-Left to Top-Right': 6,
            'Bottom-Right to Top-Left': 7,
            'Random Direction': 8,
            'Random Placement': 9,
        }
        direction = direction_map.get(direction_str, 0)
        
        particle_radius = self._safe_float(particle_settings.get('particle_radius', canonical.get('particle_radius', 10.0)), 10.0)
        overlap = self._safe_float(particle_settings.get('overlap', canonical.get('overlap', 4.0)), 4.0)
        trail_length = self._safe_float(particle_settings.get('trail_length', canonical.get('trail_length', 0.15)), 0.15)
        trail_strength = self._safe_float(particle_settings.get('trail_strength', canonical.get('trail_strength', 0.6)), 0.6)
        swirl_strength = self._safe_float(particle_settings.get('swirl_strength', canonical.get('swirl_strength', 1.0)), 1.0)
        swirl_turns = self._safe_float(particle_settings.get('swirl_turns', canonical.get('swirl_turns', 3.0)), 3.0)
        use_3d_shading = SettingsManager.to_bool(particle_settings.get('use_3d_shading', canonical.get('use_3d_shading', True)), True)
        texture_mapping = SettingsManager.to_bool(particle_settings.get('texture_mapping', canonical.get('texture_mapping', True)), True)
        wobble = SettingsManager.to_bool(particle_settings.get('wobble', canonical.get('wobble', True)), True)
        gloss_size = self._safe_float(particle_settings.get('gloss_size', canonical.get('gloss_size', 72.0)), 72.0)
        light_direction = int(particle_settings.get('light_direction', canonical.get('light_direction', 0)))
        swirl_order = int(particle_settings.get('swirl_order', canonical.get('swirl_order', 0)))
        
        if use_compositor:
            return GLCompositorParticleTransition(
                duration_ms, mode, direction, particle_radius, overlap,
                trail_length, trail_strength, swirl_strength, swirl_turns,
                use_3d_shading, texture_mapping, wobble, gloss_size,
                light_direction, swirl_order
            )
        return CrossfadeTransition(duration_ms)
    
    # Direction helpers
    
    def _get_slide_direction(self, settings: dict, type_settings: dict, settings_key: str) -> SlideDirection:
        """Get slide direction with non-repeating random support."""
        direction_str = type_settings.get('direction', 'Random') or 'Random'
        rnd_always = SettingsManager.to_bool(settings.get('random_always', False), False)
        
        if direction_str == 'Random' and not rnd_always:
            # Non-repeating random
            last_dir = type_settings.get('last_direction')
            last_enum = SLIDE_DIRECTION_MAP.get(last_dir) if isinstance(last_dir, str) else None
            candidates = [d for d in ALL_SLIDE_DIRECTIONS if d != last_enum] if last_enum in ALL_SLIDE_DIRECTIONS else ALL_SLIDE_DIRECTIONS
            direction = random.choice(candidates) if candidates else random.choice(ALL_SLIDE_DIRECTIONS)
            
            # Persist last direction
            try:
                type_settings['last_direction'] = SLIDE_DIRECTION_REVERSE.get(direction, 'Left to Right')
                settings[settings_key] = type_settings
                self._settings.set('transitions', settings)
            except Exception as e:
                logger.debug("[TRANSITION_FACTORY] Exception suppressed: %s", e)
            
            return direction
        
        return SLIDE_DIRECTION_MAP.get(direction_str, SlideDirection.LEFT)
    
    def _get_wipe_direction(self, settings: dict, wipe_settings: dict) -> WipeDirection:
        """Get wipe direction with non-repeating random support."""
        wipe_dir_str = wipe_settings.get('direction', 'Random') or 'Random'
        rnd_always = SettingsManager.to_bool(settings.get('random_always', False), False)
        
        if wipe_dir_str in WIPE_DIRECTION_MAP and not (wipe_dir_str == 'Random' and not rnd_always):
            return WIPE_DIRECTION_MAP[wipe_dir_str]
        
        # Random selection
        all_wipes = list(WIPE_DIRECTION_MAP.values())
        last_wipe = wipe_settings.get('last_direction')
        last_enum = WIPE_DIRECTION_MAP.get(last_wipe) if isinstance(last_wipe, str) else None
        candidates = [d for d in all_wipes if d != last_enum] if last_enum in all_wipes else all_wipes
        direction = random.choice(candidates) if candidates else random.choice(all_wipes)
        
        # Persist last direction
        enum_to_str = {v: k for k, v in WIPE_DIRECTION_MAP.items()}
        try:
            wipe_settings['last_direction'] = enum_to_str.get(direction, 'Left to Right')
            settings['wipe'] = wipe_settings
            self._settings.set('transitions', settings)
        except Exception as e:
            logger.debug("[TRANSITION_FACTORY] Exception suppressed: %s", e)
        
        return direction
    
    # Utility helpers
    
    @staticmethod
    def _safe_int(value, default: int) -> int:
        try:
            return int(value)
        except Exception as e:
            logger.debug("[TRANSITION_FACTORY] Exception suppressed: %s", e)
            return default
    
    @staticmethod
    def _safe_float(value, default: float) -> float:
        try:
            return float(value)
        except Exception as e:
            logger.debug("[TRANSITION_FACTORY] Exception suppressed: %s", e)
            return default
    
    def _log_selection(self, requested: str, actual: str, random_mode: bool, random_choice: Optional[str]) -> None:
        """Log transition selection."""
        try:
            if requested != actual:
                logger.info(
                    "[TRANSITIONS] Requested '%s' but instantiating '%s' (random_mode=%s, random_choice=%s)",
                    requested, actual, random_mode, random_choice,
                )
            else:
                logger.debug(
                    "[TRANSITIONS] Instantiating '%s' (requested=%s, random_mode=%s, random_choice=%s)",
                    actual, requested, random_mode, random_choice,
                )
        except Exception as e:
            logger.debug("[TRANSITION_FACTORY] Exception suppressed: %s", e)
