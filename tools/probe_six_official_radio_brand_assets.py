#!/usr/bin/env python3
"""Read-only first-party logo probe for six CarRadio PNG gaps; NEVER import art."""
import argparse
import hashlib
from html.parser import HTMLParser
from html import unescape
import json
from pathlib import Path
import re
from urllib.parse import urljoin,urlsplit,unquote
from zipfile import ZipFile

WORLD='1b0c79812d988ac4aaa368033d966de117d11e3ef5c9db66331afc5c9c750c8b'
SOURCE='b9b6c2a039e8266736ecf48500e1fbf4d8a7ff00'
SITES={
 ('AL','Radio Tirana 1'):('https://rtsh.al/radio/kanale/radio-tirana-1/','rtsh.al'),
 ('DK','Radio4'):('https://radio4.dk/','radio4.dk'),
 ('DK','Retro-Radio'):('https://retro-radio.dk/','retro-radio.dk'),
 ('GB','Big L 1'):('https://www.bigl.co.uk/','bigl.co.uk'),
 ('LT','M-1 Dance'):('https://m-1dance.fm/','m-1dance.fm'),
 ('LT','Mano FM'):('https://www.manofm.lt/','manofm.lt'),
}
WORDS={
 'Radio Tirana 1':('tirana','rtsh'),
 'Radio4':('radio4','radio-iiii','radioiiii'),
 'Retro-Radio':('retro',),
 'Big L 1':('bigl','big-l','radio-london'),
 'M-1 Dance':('m-1','m1dance','dance'),
 'Mano FM':('mano',)
}
IMAGE=re.compile(r'\.(?:svg|png|webp|jpe?g)$',re.I)
IGNORE=('favicon','apple-touch-icon','album-cover','/album/','placeholder','/artists/')

def image_url(raw,page,domain):
    if not isinstance(raw,str) or not 0<len(raw)<1500:return ''
    try:
        u=urlsplit(urljoin(page,unescape(raw.strip())))
        host=(u.hostname or '').lower().removeprefix('www.')
        if (u.scheme!='https' or u.username or u.password or
            not (host==domain or host.endswith('.'+domain)) or
            u.port not in (None,443) or u.fragment or
            not IMAGE.search(unquote(u.path))):
            return ''
        return u._replace(query='').geturl()
    except (ValueError,TypeError,AttributeError):
        return ''

class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.images=[];self.title='';self.intitle=False
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        if tag=='title':self.intitle=True
        if tag=='img':
            for attr in ('src','data-src','data-lazy-src'):
                if d.get(attr):
                    self.images.append((d[attr],d.get('alt') or d.get('title') or '',attr))
                    break
        if tag=='meta' and (d.get('property') or d.get('name')) in ('og:image','twitter:image'):
            self.images.append((d.get('content',''),'','og:image'))
    def handle_data(self,data):
        if self.intitle:self.title+=data
    def handle_endtag(self,tag):
        if tag=='title':self.intitle=False

def official_candidates(raw,url,domain,name):
    if not raw or len(raw)>2097152:raise ValueError('Empty or oversized first-party page')
    html=raw.decode('utf-8','replace')
    p=Page();p.feed(html)
    found={}
    for image,alt,kind in p.images:
        asset=image_url(image,url,domain)
        if not asset:continue
        label=(urlsplit(asset).path+' '+alt).casefold()
        if any(x in label for x in IGNORE):continue
        score=3*any(t in urlsplit(asset).path.casefold() for t in WORDS[name])
        score+=4*any(t in alt.casefold() for t in WORDS[name])
        score+=int(kind=='og:image')
        if score>0 and (asset not in found or score>found[asset]['score']):
            found[asset]={'url':asset,'alt':alt[:120],'score':score,'source_tag':kind}
    return {'page_sha256':hashlib.sha256(raw).hexdigest(),
            'page_title':' '.join(p.title.split())[:160],
            'candidates':sorted(found.values(),key=lambda x:(-x['score'],x['url']))[:18],
            'candidate_total':len(found),'html':html}

def read_gaps(gaps):
    if (gaps.get('review_only') is not True or gaps.get('world_sha256')!=WORLD or
        gaps.get('source_commit')!=SOURCE or gaps.get('still_missing_exact_matches')!=6 or
        gaps.get('previously_covered')!=65):
        raise ValueError('Unrecognized pinned missing-PNG source report')
    got={}
    for c in gaps['countries']:
        for row in c['missing_png_candidates']:
            key=(row['country'],row['name'])
            if key in got:raise ValueError('Duplicate gap')
            got[key]=row
    if set(got)!=set(SITES):raise ValueError('Six target identities differ from pinned report')
    return got

def run(gaps,world,pages,out):
    if out.exists() or out.is_symlink():raise ValueError('No overwrite of review evidence')
    if hashlib.sha256(world.read_bytes()).hexdigest()!=WORLD:
        raise ValueError('Pinned world SHA mismatch')
    items=read_gaps(json.loads(gaps.read_text(encoding='utf-8')))
    with ZipFile(world) as z:
        countries={c:{r['stationuuid']:r for r in json.loads(z.read('catalog/'+c+'.json'))['stations']}
                   for c in ('AL','DK','GB','LT')}
    results=[]
    for (country,name),(page,domain) in sorted(SITES.items()):
        row=items[(country,name)]
        pinned=countries[country].get(row['stationuuid'])
        if not pinned or pinned['name']!=name or pinned['stem']!=row['station_stem']:
            raise ValueError('Unexpected pinned station UUID/stem '+country+name)
        filename=country+'-'+re.sub('[^a-z0-9]+','-',name.casefold()).strip('-')+'.html'
        f=pages/filename
        result={'country':country,'name':name,'stationuuid':row['stationuuid'],
                'station_stem':row['station_stem'],'official_page':page,
                'archived_2024_logo_not_authorized':row['source_logo_url'],
                'accepted_new_png':0,'image_quality_passed':False}
        if not f.is_file() or not f.stat().st_size:
            result.update({'status':'OFFICIAL_PAGE_UNAVAILABLE','candidates':[]})
        else:
            found=official_candidates(f.read_bytes(),page,domain,name)
            html=found.pop('html')
            result.update(found)
            audio=pinned.get('url') or ''
            result['exact_audio_stream_in_page']=bool(audio and (
                audio in html or audio.replace('&','&amp;') in html or audio.replace('/','\\/') in html))
            if name=='Radio4' and 'RADIO IIII' in html:
                result['status']='BROADCASTER_REBRANDED_RADIO_IIII_2024_REVIEW'
            else:
                result['status']='CURRENT_LOGO_CANDIDATES_REQUIRE_IMAGE_AND_IDENTITY_QC' if found['candidates'] else 'NO_DIRECT_BRAND_IMAGE'
        results.append(result)
        print('FIRST-PARTY BRAND',json.dumps(result,ensure_ascii=False,sort_keys=True)[:6800],flush=True)
    report={'schema':1,'review_only':True,'world_sha256':WORLD,'countries':4,
            'gaps_inspected':6,'possible_first_party_image_urls':sum(len(x['candidates']) for x in results),
            'verified_new_png':0,'stations':results}
    out.mkdir(parents=True)
    (out/'six-official-broadcaster-brand-assets-review.json').write_text(
        json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print('OFFICIAL SOURCE SUMMARY',json.dumps({k:v for k,v in report.items() if k!='stations'},sort_keys=True),flush=True)
    return report

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--world',type=Path,required=True)
    p.add_argument('--gaps',type=Path,required=True)
    p.add_argument('--pages',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    run(a.gaps,a.world,a.pages,a.out)

if __name__=='__main__':main()
