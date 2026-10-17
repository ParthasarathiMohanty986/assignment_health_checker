import re
from io import BytesIO
from urllib.parse import urlsplit
from pypdf import PdfReader

def extract_pdf(data):
    if len(data)>5*1024*1024 or not data.startswith(b'%PDF-'):
        raise ValueError('Upload a valid PDF smaller than 5 MB.')
    try:
        reader=PdfReader(BytesIO(data))
        if reader.is_encrypted:
            raise ValueError('Unlock the PDF before uploading it.')
        if len(reader.pages)>30:
            raise ValueError('Use a PDF with at most 30 pages.')
        pages=[]
        for number,page in enumerate(reader.pages,1):
            text=page.extract_text() or ''
            if len(text)>15000:
                raise ValueError('A page contains too much text. Split the assignment into smaller files.')
            links=[]
            for annotation in page.get('/Annots',[]):
                action=annotation.get_object().get('/A',{})
                uri=action.get('/URI','')
                if str(uri).startswith(('https://','http://')): links.append(str(uri))
            pages.append({'number':number,'text':text,'links':links})
        if not any(p['text'].strip() for p in pages):
            raise ValueError('No selectable text found. OCR is not included yet: OCR the scanned PDF first, then upload it.')
        return pages
    except ValueError:
        raise
    except Exception:
        raise ValueError('The PDF could not be read. Export a fresh, unlocked PDF and try again.')

def propose_checks(pages):
    checks=[]; seen=set()
    for page in pages:
        urls=re.findall(r'https?://[^\s<>"\)]+',page['text'])+page.get('links',[])
        for url in urls:
            url=url.rstrip('.,;]')
            if url in seen: continue
            seen.add(url)
            path=urlsplit(url).path.lower()
            kind='csv' if path.endswith('.csv') else 'json' if path.endswith('.json') else 'http'
            checks.append({'name':f'Resource {len(checks)+1}','url':url,'kind':kind,'expected':'','expected_status':200,'page':page['number'],'requires_auth':False})
    return checks[:8]
