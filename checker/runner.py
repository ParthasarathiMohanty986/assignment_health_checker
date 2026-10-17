import csv
import io
import json
from concurrent.futures import ThreadPoolExecutor
from .network import fetch_public,NotVerifiable

DEMO_RESPONSES={
 'https://demo.invalid/sales.csv':{'status':200,'body':b'region,sales_amount\nEast,120\nWest,80\n','content_type':'text/csv','elapsed_ms':0},
 'https://demo.invalid/guide':{'status':200,'body':b'Sample assignment guide','content_type':'text/plain','elapsed_ms':0},
 'https://demo.invalid/api':{'status':200,'body':b'{"items": []}','content_type':'application/json','elapsed_ms':0},
}

def run_check(check,demo=False):
    result={'name':check['name'],'page':check['page'],'kind':check['kind'],'status':'unverified','expected':check['expected'],'detail':'','elapsed_ms':None}
    if check['requires_auth']:
        result['detail']='Protected resource skipped. Authenticated checks require an integration; no credentials were sent.';return result
    try:
        if demo:
            if check['url'] not in DEMO_RESPONSES: raise NotVerifiable('Demo mode only supports the built-in fixture URLs. Upload a real assignment for live requests.')
            response=DEMO_RESPONSES[check['url']]
        else:response=fetch_public(check['url'])
        result['elapsed_ms']=response['elapsed_ms']
        result['http_status']=response['status']
        if response['status'] in (401,403,429):
            result['detail']=f'HTTP {response["status"]}: authorization, policy, or rate limiting prevents verification.';return result
        if response['status']!=check['expected_status']:
            result.update(status='failed',detail=f'Expected HTTP {check["expected_status"]}; received HTTP {response["status"]}.');return result
        if check['kind']=='http':
            result.update(status='passed',detail=f'HTTP {response["status"]} received. Page content and workflow were not validated.');return result
        text=response['body'].decode('utf-8-sig')
        required=[s.strip() for s in check['expected'].split(',') if s.strip()]
        if check['kind']=='csv':
            if 'html' in response['content_type'].lower() or text.lstrip().lower().startswith(('<!doctype','<html')):
                raise ValueError('The resource returned HTML instead of CSV.')
            rows=csv.reader(io.StringIO(text),strict=True)
            headers=next(rows,[])
            if not headers or len(headers)!=len(set(headers)) or any(not h.strip() for h in headers):raise ValueError('CSV headers are empty or duplicated.')
            count=0
            for row in rows:
                if not row:continue
                count+=1
                if len(row)!=len(headers):raise ValueError(f'CSV row {count+1} has {len(row)} cells; expected {len(headers)}.')
            missing=sorted(set(required)-set(headers))
            result['columns']=headers[:50]
            if missing:result.update(status='failed',detail='Missing required columns: '+', '.join(missing))
            else:result.update(status='passed',detail=f'CSV parsed: {count} data rows; '+('all required columns exist.' if required else 'no required columns were specified; only structure was checked.'))
        else:
            data=json.loads(text)
            if required and not isinstance(data,dict):raise ValueError('Expected a JSON object with the specified top-level keys.')
            missing=[key for key in required if key not in data]
            result.update(status='failed' if missing else 'passed',detail='Missing JSON keys: '+', '.join(missing) if missing else 'Valid JSON; '+('required top-level keys exist.' if required else 'no schema requirements specified.'))
    except NotVerifiable as error:result['detail']=str(error)
    except (ValueError,UnicodeError,csv.Error) as error:result.update(status='failed',detail=str(error)[:500])
    except Exception:result['detail']='Unexpected checker error. No pass/fail conclusion was made.'
    return result

def run_all(checks,demo=False):
    with ThreadPoolExecutor(max_workers=4) as pool:
        return list(pool.map(lambda c:run_check(c,demo),checks))
