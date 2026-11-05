import pypdfium2 as pdfium
from PIL import Image, ImageDraw
from pathlib import Path
base=Path('C:/Users/Nigail/Desktop/Semester 7/DevOps')
out=Path('tmp/notes')
for n in ['AWS-RDS.pdf','AutoScaling.pdf','Elastic load Balancer.pdf']:
 d=pdfium.PdfDocument(base/n)
 for start in range(0,len(d),6):
  sheet=Image.new('RGB',(1800,1500),'white')
  draw=ImageDraw.Draw(sheet)
  for j in range(start,min(start+6,len(d))):
   im=d[j].render(scale=1.2).to_pil()
   im.thumbnail((890,460))
   x=(j-start)%2*900
   y=(j-start)//2*500
   sheet.paste(im,(x,y+25))
   draw.text((x+5,y+5),str(j+1),fill='black')
  sheet.save(out/(n+str(start)+'.png'))

