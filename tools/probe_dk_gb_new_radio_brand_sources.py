#!/usr/bin/env python3
"""New official DK and GB brand sources: read-only, no artwork import."""
import argparse,hashlib,json,re
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urljoin,urlsplit
from zipfile import ZipFile
from probe_six_official_radio_brand_assets import read_gaps
WORLD_SHA="04dbf8bee8101da8af6042f236f86e7949635826550b2d506f1f45cf7886e95d"
PAGES={"radio4-home":"https://radio4.dk/",
 "radio4-about":"https://radio4.dk/om-radio4/",
 "radio4-listen":"https://radio4.dk/saadan-lytter-du",
 "radio4-designer":"https://www.tobiasroeder.com/work/radio-iiii",
 "radioplayer-dk":"https://mereradio.dk/",
 "radioplayer-about":"https://mereradio.dk/om-mereradio",
 "bigl-home":"https://www.bigl.co.uk/"}
WORDS=("radio4","radio-iiii","radioiiii","logo","brand","bigl","big-l")
EXCLUDE=("favicon","apple-touch","/podcast/","/episode/","/album/","/avatar/","/artist/","placeholder")
class Page(HTMLParser):
 def __init__(self):
  super().__init__(convert_charrefs=True)
  self.title="";self.in_title=False;self.images=[];self.meta=[];self.svgs=0
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=="title":self.in_title=True
  if tag=="svg":self.svgs+=1
  if tag=="img":self.images.append((a.get("src") or a.get("data-src") or "",a.get("alt") or "","img"))
  if tag=="link":self.images.append((a.get("href") or "",a.get("title") or "","link"))
  if tag=="meta":
   k=a.get("property") or a.get("name") or "";v=a.get("content") or ""
   if k.startswith(("og:","twitter:")):self.meta.append((k,v[:500]))
   if k in ("og:image","og:image:url","twitter:image"):self.images.append((v,"",k))
 def handle_endtag(self,tag):
  if tag=="title":self.in_title=False
 def handle_data(self,data):
  if self.in_title:self.title+=data
def image_url(raw,page):
 if not isinstance(raw,str) or not 1<=len(raw)<=1200:return ""
 try:
  u=urlsplit(urljoin(page,raw.strip().split()[0]))
  host=(u.hostname or "").lower().removeprefix("www.")
  origin=(urlsplit(page).hostname or "").lower().removeprefix("www.")
  if (u.scheme!="https" or not host or u.username or u.password or
      u.port not in (None,443) or u.fragment or not (host==origin or host.endswith("."+origin)) or
      not re.search(r"\.(svg|png|webp|jpe?g)$",u.path,re.I)):return ""
  return u._replace(query="").geturl()
 except (ValueError,IndexError):return ""
def summarize(url,data):
 if not isinstance(data,bytes) or not 1<=len(data)<=5000000:raise ValueError("Invalid page")
 text=data.decode("utf-8","replace");p=Page();p.feed(text);chosen={}
 svg_evidence=[]
 for m in re.finditer(r"<svg\b[^>]*>[\s\S]*?</svg>",text,re.I):
  before=text[max(0,m.start()-240):m.start()]
  tag=m.group(0).split(">",1)[0]
  clues=(before+" "+tag).lower()
  if len(svg_evidence)<32 and (m.start()<20000 or any(x in clues for x in ("logo","header","navbar","brand","radio4"))):
   svg_evidence.append({"position":m.start(),"sha256":hashlib.sha256(m.group(0).encode()).hexdigest(),
    "bytes":len(m.group(0)),"start_tag":tag[:230],
    "before":before[-200:],"path_count":len(re.findall(r"<path\b",m.group(0),re.I))})
 for raw,alt,kind in p.images:
  link=image_url(raw,url)
  if not link:continue
  key=(urlsplit(link).path+" "+alt).lower()
  if any(t in key for t in EXCLUDE):continue
  score=sum(t in key for t in WORDS)+int(kind.startswith(("og:","twitter:")))
  if score:chosen[link]={"url":link,"alt":alt[:100],"via":kind,"score":score}
 return {"html_sha256":hashlib.sha256(data).hexdigest(),"bytes":len(data),
  "title":" ".join(p.title.split())[:160],"has_radio_iiii":"RADIO IIII" in text,
  "has_big_l":"Big L" in text or "BIG L" in text,"embedded_svg":p.svgs,
  "meta":[[k,v] for k,v in p.meta if k in ("og:title","og:site_name","og:image","og:image:alt")][:14],
  "firstparty_candidates":sorted(chosen.values(),key=lambda x:-x["score"])[:20],
  "inline_svg_evidence":svg_evidence}
def run(world,gaps,pages,out):
 if out.exists():raise ValueError("Refuse overwriting previous review")
 raw=world.read_bytes()
 if hashlib.sha256(raw).hexdigest()!=WORLD_SHA:raise ValueError("Incorrect 39665-world SHA")
 with ZipFile(world) as z:
  idx=json.loads(z.read("index.json"))
  if idx["country_count"]!=224 or idx["station_count"]!=48219 or sum(x["logos_found"] for x in idx["countries"].values())!=39665 or idx["countries"]["DK"]["logos_found"]!=162:raise ValueError("Old world snapshot")
  catalogs={c:json.loads(z.read("catalog/"+c+".json"))["stations"] for c in ("DK","GB")}
 gaps=read_gaps(json.loads(gaps.read_text(encoding="utf-8")));targets=[]
 for code,name in (("DK","Radio4"),("GB","Big L 1")):
  evidence=gaps[(code,name)];rows=[r for r in catalogs[code] if r["stationuuid"]==evidence["stationuuid"]]
  if len(rows)!=1 or rows[0]["name"]!=name or rows[0]["stem"]!=evidence["station_stem"]:raise ValueError("Wrong pinned stream identity")
  row=rows[0];targets.append({"country":code,"station":name,"uuid":row["stationuuid"],"stream":row["url"],"homepage":row["homepage"],"old_logo_rejected":True})
 sources={}
 for label,url in PAGES.items():
  page=pages/(label+".html")
  sources[label]={"url":url,"status":"NO_RESPONSE" if not page.is_file() else "HTML_REVIEW_ONLY","accepted_png":0}
  if page.is_file():sources[label].update(summarize(url,page.read_bytes()))
  print("OFFICIAL SOURCE",label,json.dumps(sources[label],ensure_ascii=False,sort_keys=True)[:6500],flush=True)
 report={"schema":1,"review_only":True,"source_world_sha256":WORLD_SHA,"countries_checked":2,"sources_checked":len(PAGES),"targets":targets,"sources":sources,"new_png_verified":0}
 out.mkdir(parents=True)
 (out/"radio4-bigl-new-firstparty-sources.json").write_text(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf-8")
 print("PINNED TARGETS",json.dumps(targets,sort_keys=True),flush=True)
 return report
if __name__=="__main__":
 a=argparse.ArgumentParser()
 for k in ("world","gaps","pages","out"):a.add_argument("--"+k,type=Path,required=True)
 v=a.parse_args();run(v.world,v.gaps,v.pages,v.out)
