import io
import json
import socket
from unittest.mock import patch,Mock
from django.test import TestCase,SimpleTestCase,override_settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
from .extract import extract_pdf,propose_checks
from .network import resolve_public,NotVerifiable,fetch_public
from .runner import run_check
from .models import Assignment,Run
from . import ai

def pdf_fixture():
    writer=PdfWriter();page=writer.add_blank_page(width=612,height=792)
    font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
    page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
    stream=DecodedStreamObject();stream.set_data(b'BT /F1 12 Tf 50 700 Td (Sales assignment: https://example.com/sales.csv) Tj ET')
    page[NameObject('/Contents')]=writer._add_object(stream)
    buffer=io.BytesIO();writer.write(buffer);return buffer.getvalue()

def check(kind='csv',expected='region,revenue'):
    return {'name':'Test resource','url':'https://example.com/data','kind':kind,'expected':expected,'expected_status':200,'page':1,'requires_auth':False}

class ParserTests(SimpleTestCase):
    def test_pdf_text_urls_and_pages(self):
        pages=extract_pdf(pdf_fixture());self.assertEqual(pages[0]['number'],1)
        checks=propose_checks(pages);self.assertEqual(checks[0]['kind'],'csv');self.assertEqual(checks[0]['expected'],'')
    def test_invalid_and_scanned_pdf(self):
        with self.assertRaises(ValueError):extract_pdf(b'not a pdf')
        writer=PdfWriter();writer.add_blank_page(100,100);out=io.BytesIO();writer.write(out)
        with self.assertRaisesRegex(ValueError,'OCR'):extract_pdf(out.getvalue())

class CheckTests(SimpleTestCase):
    def result(self,body,kind='csv',expected='region,revenue',status=200):
        with patch('checker.runner.fetch_public',return_value={'status':status,'body':body,'content_type':'text/plain','elapsed_ms':1}):
            return run_check(check(kind,expected))
    def test_csv_pass_missing_and_malformed(self):
        self.assertEqual(self.result(b'region,revenue\nEast,12')['status'],'passed')
        self.assertIn('revenue',self.result(b'region,sales\nEast,12')['detail'])
        self.assertEqual(self.result(b'region,revenue\nEast,12,extra')['status'],'failed')
        self.assertEqual(self.result(b'<html>Login</html>')['status'],'failed')
    def test_json_keys_and_invalid_body(self):
        self.assertEqual(self.result(b'{"result":1}','json','result')['status'],'passed')
        self.assertEqual(self.result(b'{"items":[]}','json','result')['status'],'failed')
        self.assertEqual(self.result(b'not json','json','result')['status'],'failed')
    def test_auth_and_rate_limit_unverified(self):
        c=check();c['requires_auth']=True
        with patch('checker.runner.fetch_public') as fetch:
            self.assertEqual(run_check(c)['status'],'unverified');fetch.assert_not_called()
        self.assertEqual(self.result(b'','http','',401)['status'],'unverified')
        self.assertEqual(self.result(b'','http','',500)['status'],'failed')
    def test_demo_never_fetches_network(self):
        c=check();c['url']='https://demo.invalid/sales.csv'
        with patch('checker.runner.fetch_public') as fetch:
            self.assertEqual(run_check(c,True)['status'],'failed');fetch.assert_not_called()
    def test_private_and_query_urls_blocked(self):
        for ip in ('127.0.0.1','10.0.0.1','169.254.169.254','::1','192.168.1.2'):
            with patch('checker.network.socket.getaddrinfo',return_value=[(socket.AF_INET,socket.SOCK_STREAM,6,'',(ip,80))]):
                with self.assertRaises(NotVerifiable):resolve_public('http://example.com/')
        for url in ('file:///etc/passwd','http://user:pass@example.com','https://example.com/?token=abc','http://example.com:22/'):
            with self.assertRaises(NotVerifiable):resolve_public(url)
    def test_public_dns_resolution(self):
        with patch('checker.network.socket.getaddrinfo',return_value=[(socket.AF_INET,socket.SOCK_STREAM,6,'',('93.184.216.34',443))]):
            self.assertEqual(resolve_public('https://example.com/')[2],'93.184.216.34')

class WorkflowTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user(username='teacher',password='test-only')
        self.client.force_login(self.user)
    def test_upload_review_run_and_export(self):
        response=self.client.post('/upload/',{'title':'Assignment','pdf':SimpleUploadedFile('assignment.pdf',pdf_fixture(),content_type='application/pdf')})
        self.assertEqual(response.status_code,302)
        obj=Assignment.objects.get();self.assertFalse(obj.approved)
        self.client.post(f'/assignments/{obj.pk}/run/');self.assertEqual(Run.objects.count(),0)
        c=obj.checks[0];c['expected']='region,revenue'
        post={'form-TOTAL_FORMS':'2','form-INITIAL_FORMS':'1','approve':'yes',**{f'form-0-{key}':value for key,value in c.items() if key!='requires_auth'},'form-1-name':'','form-1-url':'','form-1-kind':'http','form-1-expected':'','form-1-expected_status':'200','form-1-page':'1'}
        response=self.client.post(f'/assignments/{obj.pk}/review/',post);self.assertEqual(response.status_code,302)
        obj.refresh_from_db();self.assertTrue(obj.approved)
        with patch('checker.runner.fetch_public',return_value={'status':200,'body':b'region,sales\nEast,1','content_type':'text/csv','elapsed_ms':1}):
            self.client.post(f'/assignments/{obj.pk}/run/')
        run=Run.objects.get();self.assertEqual(run.failed,1)
        self.assertEqual(self.client.get(f'/assignments/{obj.pk}/').status_code,200)
        self.assertEqual(self.client.get(f'/runs/{run.pk}/export/').json()['results'][0]['status'],'failed')
    def test_ownership_and_consent(self):
        other=get_user_model().objects.create_user(username='other')
        obj=Assignment.objects.create(owner=other,title='Private')
        self.assertEqual(self.client.get(f'/assignments/{obj.pk}/').status_code,404)
        obj.owner=self.user;obj.save();run=Run.objects.create(assignment=obj,results=[{'kind':'csv','expected':'x','detail':'Missing x','status':'failed'}])
        with patch('checker.ai.suggest_fixes') as suggest:
            self.client.post(f'/runs/{run.pk}/suggest/');suggest.assert_not_called()
    @override_settings(DEBUG=False)
    def test_local_login_disabled_in_production(self):
        self.client.logout();self.assertRedirects(self.client.post('/local-login/'), '/', fetch_redirect_response=False)

class AITests(SimpleTestCase):
    def test_payload_excludes_urls_and_source(self):
        run=Mock(results=[{'kind':'csv','expected':'revenue','detail':'Missing revenue at https://example.com?key=abc','status':'failed'}])
        payload=json.dumps(ai.evidence_payload(run));self.assertNotIn('https://',payload);self.assertNotIn('key=abc',payload)
    @patch.dict('os.environ',{'GROQ_API_KEY':'test-key'})
    @patch('checker.ai.httpx.post')
    def test_ai_calls_groq_and_reads_response(self,post):
        post.return_value=Mock(status_code=200)
        post.return_value.json.return_value={'choices':[{'finish_reason':'stop','message':{'content':'Confirm the dataset schema.'}}]}
        self.assertEqual(ai.suggest_fixes([]),'Confirm the dataset schema.')
        self.assertEqual(post.call_args.args[0],'https://api.groq.com/openai/v1/chat/completions')


class GuestWorkspaceTests(TestCase):
    def test_guest_entry_and_isolation(self):
        from django.test import Client
        first, second = Client(), Client()
        self.assertEqual(first.get('/').status_code, 200)
        owner_id = first.session['_auth_user_id']
        assignment = Assignment.objects.create(owner_id=owner_id, title='Private guest assignment')
        self.assertEqual(first.get(f'/assignments/{assignment.pk}/').status_code, 200)
        self.assertEqual(second.get('/').status_code, 200)
        self.assertNotEqual(owner_id, second.session['_auth_user_id'])
        self.assertEqual(second.get(f'/assignments/{assignment.pk}/').status_code, 404)
        first.get('/')
        self.assertEqual(first.session['_auth_user_id'], owner_id)
        self.assertFalse(get_user_model().objects.get(pk=owner_id).has_usable_password())

    def test_health_does_not_create_guests(self):
        self.assertEqual(self.client.get('/health/').status_code, 200)
        self.assertEqual(get_user_model().objects.count(), 0)
