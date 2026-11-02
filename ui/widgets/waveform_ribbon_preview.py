"""User-triggered production-scene preview: finite synthetic samples, no preview clock or engine."""
from __future__ import annotations
from types import SimpleNamespace
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QCheckBox, QSlider


def render_samples(parameters, *, turned=False, size=(480,300)):
    """Render three explicit quiet/middle/peak fixtures through the production body and retained scene owners."""
    from core.waveform_ribbon_dynamics import WaveformDynamics
    from widgets.spotify_visualizer.waveform_ribbon_parameters import CompiledWaveformSettings
    from rendering.quick.visualizer.implementations.waveform_ribbon import physical_view
    from core.settings.waveform_ribbon_camera import scene_raster_support
    from rendering.quick.scene3d.waveform import WaveformScene
    from rendering.quick.offscreen_target import OffscreenRenderTarget
    from PySide6.QtGui import QOpenGLContext
    config=CompiledWaveformSettings(parameters)
    camera=dict(parameters)
    if turned:camera['waveform_ribbon_turn']=.22
    width,height=size
    caller=QOpenGLContext.currentContext()
    caller_surface=caller.surface() if caller is not None else None
    target=OffscreenRenderTarget(width,height,label='waveform Settings preview');scene=WaveformScene()
    samples=[]
    try:
        card=SimpleNamespace(viewport=(0,0,width,height),logical_size=(float(width),float(height)),
            quad_vao=target.vao,matrix_values=(2/width,0,0,0,0,-2/height,0,0,0,0,1,0,-1,1,0,1))
        for drive in (0.,.45,.9):
            model=WaveformDynamics(config.controls)
            for _ in range(64):model.advance(1/90,bands=(0.,0.,0.),intensity=0.,presence=0.)
            for index in range(180):
                snapshot=model.advance(1/90,bands=(drive,.8*drive,.7*drive),intensity=drive,
                                       presence=1.,hit=.9 if drive and index in (30,90,150) else 0.)
            recipe=config.scene(snapshot)
            support=(scene_raster_support(snapshot.packet,recipe,snapshot.travel,now=snapshot.time,viewport=size,
                burst_payload=snapshot.particles,burst_origin=snapshot.particle_origin,strand_payload=snapshot.strands)
                if camera['waveform_ribbon_camera_projection']=='Orthographic' else None)
            view,projection,eye,lens=physical_view(camera,width/height,geometry_bounds=support)
            if recipe.sparks is not None:
                for _ in range(8):
                    if scene.bursts.prepare_step():break
                else:raise RuntimeError('Waveform preview spark preparation did not complete')
            target.bind()
            scene.render(snapshot.packet,capacity=256,now=snapshot.time,travel=snapshot.travel,recipe=recipe,
                size=size,view=view,projection=projection,eye=eye,camera_lens=lens,card=card,
                react=snapshot.passage,burst_payload=snapshot.particles,burst_origin=snapshot.particle_origin,
                strand_payload=snapshot.strands,strand_origin=snapshot.strand_origin)
            pixels=target.read_rgba()
            samples.append(QImage(pixels.data,width,height,width*4,QImage.Format.Format_RGBA8888).copy())
        return samples
    finally:
        try:
            with target.current():scene.release()
        finally:
            target.close()
            if caller is not None and caller_surface is not None and not caller.makeCurrent(caller_surface):
                raise RuntimeError('Could not restore caller context after waveform preview')


class WaveformPreview(QWidget):
    """Refresh explicitly after tuning; scrubbing cached images never allocates GL resources."""
    def __init__(self, read_parameters, parent=None):
        super().__init__(parent)
        self._read_parameters=read_parameters;self._images=[]
        layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0)
        row=QHBoxLayout();layout.addLayout(row)
        self.refresh=QPushButton('Preview quiet → peak',self);row.addWidget(self.refresh)
        self.turned=QCheckBox('Turned view',self);row.addWidget(self.turned);row.addStretch()
        self.image=QLabel('Render the current controls to inspect body, colours, particles and mist.',self)
        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter);self.image.setWordWrap(True);layout.addWidget(self.image)
        self.scrub=QSlider(Qt.Orientation.Horizontal,self);self.scrub.setRange(0,2);self.scrub.setEnabled(False)
        self.scrub.setToolTip('Quiet / middle / peak synthetic snapshots at the same explicit scene time.')
        layout.addWidget(self.scrub)
        self.refresh.clicked.connect(self._render);self.scrub.valueChanged.connect(self._show)

    def _render(self):
        self.refresh.setEnabled(False)
        try:
            self._images=[QPixmap.fromImage(image) for image in render_samples(self._read_parameters(),
                                                                            turned=self.turned.isChecked())]
            self.scrub.setEnabled(True);self._show(self.scrub.value())
        except Exception:
            from core.logging.logger import get_logger
            get_logger(__name__).exception('Waveform production-scene preview failed')
            self.image.setText('Preview failed. See the application log for the rendering error.')
        finally:self.refresh.setEnabled(True)

    def _show(self,index):
        if self._images:self.image.setPixmap(self._images[index])
