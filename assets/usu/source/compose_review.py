"""Arrange unchanged Blender renders beside the approved reference for review."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

PROJECT=Path(r"F:\Programming\Apps\ShittyRandomPhotoScreenSaver")
ASSET=PROJECT/"assets"/"usu"
reference=Image.open(PROJECT/"tmp"/"UsuForModelling.png").convert("RGB")
font=ImageFont.truetype(r"C:\Windows\Fonts\segoeui.ttf",24)
small=ImageFont.truetype(r"C:\Windows\Fonts\segoeui.ttf",20)
views=[("FRONT","front",(10,175,377,875)),("SIDE","side",(405,175,697,875)),
       ("BACK","back",(701,175,1064,875)),("3/4","three_quarter",(1073,175,1430,875))]
comparison=Image.new("RGB",(1920,1670),(244,244,244))
draw=ImageDraw.Draw(comparison)
draw.text((24,8),"APPROVED TURNAROUND",fill=(25,25,25),font=font)
draw.text((24,838),"CURRENT STATIC DRAFT — visual approval pending",fill=(25,25,25),font=font)
sheet=Image.new("RGB",(1920,626),(244,244,244))
sheet_draw=ImageDraw.Draw(sheet)
for i,(label,stem,ref_crop) in enumerate(views):
    draw.text((i*480+220,45),label,fill=(25,25,25),font=small)
    ref=reference.crop(ref_crop)
    ref=ref.resize((round(ref.width*750/ref.height),750),Image.Resampling.LANCZOS)
    comparison.paste(ref,(i*480+(480-ref.width)//2,78))
    render=Image.open(ASSET/"renders"/f"Usu_{stem}.png").convert("RGB")
    assert render.size == (1000,1200), (stem,render.size)
    draft=render.crop((160,66,840,1132))
    draft=draft.resize((round(draft.width*750/draft.height),750),Image.Resampling.LANCZOS)
    comparison.paste(draft,(i*480+(480-draft.width)//2,886))
    sheet_draw.text((i*480+205,9),label,fill=(25,25,25),font=font)
    sheet.paste(render.resize((480,576),Image.Resampling.LANCZOS),(i*480,44))
comparison.save(ASSET/"renders"/"Usu_Reference_Comparison.png")
sheet.save(ASSET/"renders"/"Usu_Static_Views.png")

free_views=[("OBLIQUE FRONT","oblique_front"),("OBLIQUE REAR","oblique_rear"),
            ("HIGH REAR","high_rear"),("LOW FRONT","low_front"),
            ("HIGH SIDE","high_side")]
free_sheet=Image.new("RGB",(1920,1624),(244,244,244))
free_draw=ImageDraw.Draw(free_sheet)
for i,(label,stem) in enumerate(free_views):
    x,y=(i%3)*640,(i//3)*812
    free_draw.text((x+24,y+9),label,fill=(25,25,25),font=font)
    render=Image.open(ASSET/"renders"/f"Usu_{stem}.png").convert("RGB")
    assert render.size == (1000,1200), (stem,render.size)
    free_sheet.paste(render.resize((640,768),Image.Resampling.LANCZOS),(x,y+40))
free_draw.multiline_text((1304,900),"STATIC SHAPE REVIEW\n\nSame geometry in every view.\nVisual approval pending.",
                         fill=(25,25,25),font=font,spacing=12)
free_sheet.save(ASSET/"renders"/"Usu_Free_Angles.png")
