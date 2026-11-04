"""A small deterministic HTTP fixture, independent of the production exporter."""
import gzip
import hashlib
import io
import json


def data(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()


def country_fixture(rows):
    groups = {}
    for row in rows:
        groups.setdefault(row['group'], []).append({key: row[key] for key in ('name','url','reference','group')})
    names = ['Slovensko','Čechy'] + [name for name in groups if name not in ('Slovensko','Čechy')]
    files, entries = {}, []
    reserved = {'SK','CZ','DE'}
    codes = (chr(a)+chr(b) for a in range(65,91) for b in range(65,91)
             if chr(a)+chr(b) not in reserved)
    def pack(items, code, name, kind):
        raw = data(items); blob = gzip.compress(raw, mtime=0)
        digest = hashlib.sha256(blob).hexdigest()
        path = ('search' if code == 'WORLD' else 'countries/'+code) + '/' + digest + '.json.gz'
        files[path] = blob
        return dict(id=code,name=name,kind=kind,stations=len(items),path=path,
                    sha256=digest,version=digest,bytes=len(blob),decoded_bytes=len(raw),
                    decoded_sha256=hashlib.sha256(raw).hexdigest())
    for name in names:
        code = {'Slovensko':'SK','Čechy':'CZ','Germany':'DE'}.get(name) or next(codes)
        entries.append(pack(groups[name], code, name, 'country'))
    search = pack([row for name in names for row in groups[name]], 'WORLD','All groups','search')
    manifest = dict(schema=1,countries=entries,search=search)
    manifest['revision'] = hashlib.sha256(data(manifest)).hexdigest()
    files['country-manifest.json'] = data(manifest)
    return manifest, files


class Backend:
    def __init__(self, files):
        self.files, self.requests = files, []

    def __call__(self, request, **kwargs):
        path = request.full_url.split('/catalog/global/',1)[1]
        self.requests.append(path)
        return io.BytesIO(self.files[path])


def rows(group, count=3, start=1):
    return [dict(name='Radio '+str(number),url='https://radio.example/'+str(number),
                 reference='4097:0:2:%X:1:ED:0:0:0:0'%number,group=group)
            for number in range(start,start+count)]
