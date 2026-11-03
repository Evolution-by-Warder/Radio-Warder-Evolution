"""Bounded radio metadata repair and explicitly verified catalogue identities."""
import re
import unicodedata


def norm(value):
    value=unicodedata.normalize('NFKD',str(value or '').casefold())
    return ' '.join(''.join(c for c in value if not unicodedata.combining(c)
                            and c not in "'’‘ʼ").split())


def split_stream(value):
    text=' '.join(str(value or '').split())
    # Receiver-proven file tag: NN - Title - Artist. Do not strip years,
    # alphanumeric act names, or numbers without two actual delimiters.
    numbered=re.fullmatch(r'\d{1,3}\s+[-–—]\s+(.+)\s+[-–—]\s+([^-–—]+)',text)
    if numbered:
        return numbered.group(2).strip(),numbered.group(1).strip()
    for separator in (' - ',' – ',' — ',': '):
        if separator in text:
            artist,title=(part.strip() for part in text.split(separator,1))
            if artist and title:return repair_pair(artist,title)
    # Some ICY tags omit spaces around the separator. Require full phrases
    # on both sides so a lone hyphenated artist (Jay-Z/Jean-Michel Jarre)
    # never becomes a made-up song. Existing spaced formats take priority.
    for separator in ('-','–','—'):
        if text.count(separator)==1:
            artist,title=(v.strip() for v in text.split(separator,1))
            if len(artist.split())>=2 and len(title.split())>=2:
                return repair_pair(artist,title)
    return '',''


def repair_pair(artist,title):
    artist,title=str(artist or '').strip(),str(title or '').strip()
    if re.fullmatch(r'\d{1,3}',artist) and any(s in title for s in (' - ',' – ',' — ')):
        return split_stream(artist+' - '+title)
    tagged=re.fullmatch(r'\d{1,3}_\s*(\S+(?:\s+\S+)+)',artist)
    if tagged:artist=tagged.group(1)
    return artist,title


# These are full, curated identities, never surname/substring guesses.
PERSON_ALIASES={
 'm. zbirka':'miroslav zbirka','m.zbirka':'miroslav zbirka',
 'miro zbirka':'miroslav zbirka','zbirka miroslav':'miroslav zbirka',
 'necar vaclav':'vaclav neckar','neckar vaclav':'vaclav neckar',
 'sima magusinova':'sima martausova',
 'sima magusinova (martausova)':'sima martausova',
 'simona martausova':'sima martausova',
 'i.m.t. smile':'imt smile',
 'kroky f. janecka':'kroky frantiska janecka',
 'kroky f.janecka':'kroky frantiska janecka',
 'a.m.o.':'amo',
}
DISPLAY={
 'miroslav zbirka':'Miroslav Žbirka','vaclav neckar':'Václav Neckář',
 'sima martausova':'Sima Martausová','imt smile':'IMT Smile',
 'michal david':'Michal David','kroky frantiska janecka':'Kroky Františka Janečka',
 'amo':'A.M.O.','polemic':'Polemic',
 'helena vondrackova':'Helena Vondráčková','jiri korn':'Jiří Korn',
}
FEATURE=re.compile(r'\s*\((?:feat\.?|ft\.?|featuring)\s+([^()]+)\)\s*$',re.I)
FEATURE_INLINE=re.compile(r'\s+(?:feat\.?|ft\.?|featuring)\s+([^()]+)\s*$',re.I)
SEPARATORS=re.compile(r'\s+(?:feat\.?|ft\.?|featuring|and|with)\s+|\s*[&,;]\s*',re.I)


def credit(artist,title):
    artist,title=repair_pair(artist,title)
    featured=FEATURE.search(title) or FEATURE_INLINE.search(title)
    if featured:
        artist=artist+' & '+featured.group(1)
        title=title[:featured.start()].strip().rstrip(',').rstrip()
    return artist,title


def roster(value):
    parts=[part.strip() for part in SEPARATORS.split(norm(value)) if part.strip()]
    expanded=[]
    for part in parts:
        names=re.split(r'\s+/\s+',part)
        expanded.extend(names if len(names)>1 and all(len(n.split())>=2 for n in names) else [part])
    return tuple(sorted(PERSON_ALIASES.get(part,part) for part in expanded))


def title_key(value,artists=()):
    value=norm(value).replace(',','')
    # Only documented names of these recordings; never remove arbitrary
    # version suffixes such as Live, Remix, Acoustic or Instrumental.
    if artists==('vaclav neckar',) and value in (
       'svatovitsky chram','svatovitsky chram (chram sv. vita)',
       'chram sv. vita',
       'svatovitsky chram (winchester cathedral)',
       'svatovitsky chram /chram sv. vita/ (winchester cathedral)'):
        return 'svatovitsky chram'
    if artists==('darinka rolincova',) and value=='az raz budem uvitelkou':
        return 'az raz budem ucitelkou'
    if artists in (('helena vondrackova',),('helena vondrackova','jiri korn')) and value in (
       'kazda trampota ma svou mez','kazda trampota ma svou mez (rest your love on me)'):
        return 'kazda trampota ma svou mez'
    if artists==('peter bic project',) and value in ('stromy','stromy (original version)'):
        return 'stromy'
    if artists==('pavel roth',) and value in (
       'krasnejsi nez ruze','krasnejsi nez ruze (maliconia)',
       'krasnejsi nez ruze (malinconia)','malinconia (krasnejsi nez ruze)'):
        return 'krasnejsi nez ruze (malinconia)'
    return ' '.join(re.sub(r'[()[\]{}–—-]',' ',value).split())


def identity_options(artist,title):
    artist,title=credit(artist,title)
    options={roster(artist)}
    parts=re.split(r'\s+a\s+',norm(artist))
    if len(parts)>1 and all(len(part.split())>=2 for part in parts):
        options.add(tuple(sorted(PERSON_ALIASES.get(p,p) for p in parts)))
    result=set()
    for names in options:
        track=title_key(title,names)
        # Complete recording-specific credit variants, supported by publisher
        # catalogue/artist credits. Extra guests are never silently removed.
        if track=='biely kvet' and names==('limit','miroslav zbirka'):
            names=('miroslav zbirka',)
        elif track=='viac' and names in (('imt smile','ivan tasler'),('ivan tasler',)):
            names=('imt smile',)
        elif track=='hrajte trubky' and names==('vidiek',):
            names=('boban markovic','marko markovic','vidiek')
        elif track=='kazda trampota ma svou mez' and names==('helena vondrackova',):
            names=('helena vondrackova','jiri korn')
        elif track=='taliansky muzikal' and names in (
             ('julia heckova',),('julia a peter heckovci',),('heckovci',),
             ('julia heckova','peter hecko')):
            names=('julia a peter heckovci',)
        result.add((names,track))
    return result


def same_recording(row,artist,title):
    if not artist or not title or not row.get('artistName') or not row.get('trackName'):return False
    got=identity_options(row.get('artistName',''),row.get('trackName',''))
    return bool(got.intersection(identity_options(artist,title)) or
                got.intersection(identity_options(title,artist)))


def query_pair(artist,title):
    artist,title=credit(artist,title)
    names,track=sorted(identity_options(artist,title))[0]
    # Normalize only when an actual curated difference is present. Unknown
    # names keep their original spelling and all credited performers.
    normalized=' & '.join(DISPLAY.get(n,n) for n in names)
    if roster(artist)!=names or any(norm(p) in PERSON_ALIASES for p in SEPARATORS.split(artist)):
        artist=normalized
    if names==('darinka rolincova',) and track=='az raz budem ucitelkou':
        title='Až raz budem učiteľkou'
    elif track=='krasnejsi nez ruze (malinconia)' and names==('pavel roth',):
        title='Krásnější než růže (Malinconia)'
    elif track=='svatovitsky chram' and names==('vaclav neckar',):
        title='Svatovítský chrám'
    return artist,title


def site_artists(artist,title):
    artist,title=query_pair(artist,title)
    lead=SEPARATORS.split(artist)[0].strip()
    names=[lead]
    if roster(artist)==('boban markovic','marko markovic','vidiek') and title_key(title)=='hrajte trubky':
        names=['Vidiek']
    elif norm(lead)=='sima martausova':
        names=['Sima Magušinová (Martausová)','Sima Martausová','Sima Magušinová']
    elif norm(lead)=='miroslav zbirka':
        names=['Miro Žbirka','Miroslav Žbirka']
    elif norm(lead)=='julia a peter heckovci':
        names=['Hečkovci','Júlia Hečková','Júlia a Peter Hečkovci']
    return list(dict.fromkeys(names))[:3]


def site_titles(artist,title):
    artist,title=query_pair(artist,title)
    names,track=sorted(identity_options(artist,title))[0]
    if names==('pavel roth',) and track=='krasnejsi nez ruze (malinconia)':
        return ['Krásnější než růže','Krásnější než růže (Malinconia)','Malinconia (Krásnější než růže)']
    return [title]


def station_profile(name):
    name=norm(name)
    return 'skcz' if (re.search(r'\bceskoslovensk\w*\b',name) or
                     re.search(r'\b(?:slovenske|ceske) hity\b',name) or
                     re.search(r'\b(?:sk\s*[/&-]\s*cz|cz\s*[/&-]\s*sk)\b',name)) else 'global'
