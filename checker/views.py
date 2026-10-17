import json
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model,login
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse,HttpResponseForbidden
from django.shortcuts import render,redirect,get_object_or_404
from django.views.decorators.http import require_POST
from .models import Assignment,Run
from .forms import UploadForm,CheckFormSet
from .extract import extract_pdf,propose_checks
from .runner import run_all
from . import ai

@require_POST
def local_login(request):
    if not settings.DEBUG or request.META.get('REMOTE_ADDR') not in ('127.0.0.1','::1'):
        return HttpResponseForbidden('Local workspace is available only on localhost in development.')
    user,created=get_user_model().objects.get_or_create(username='local-instructor')
    if created:user.set_unusable_password();user.save()
    login(request,user)
    return redirect('index')

@login_required
def index(request):
    assignments=Assignment.objects.filter(owner=request.user).order_by('-created_at')
    return render(request,'checker/index.html',{'assignments':assignments,'upload_form':UploadForm(),'ai_ready':ai.configured()})

@login_required
@require_POST
def upload(request):
    form=UploadForm(request.POST,request.FILES)
    if form.is_valid():
        try:
            file=form.cleaned_data['pdf']
            if file.size>5*1024*1024:raise ValueError('PDF size must be under 5 MB.')
            pages=extract_pdf(file.read())
            obj=Assignment.objects.create(owner=request.user,title=form.cleaned_data['title'],filename=file.name[:255],pages=pages,checks=propose_checks(pages))
            messages.success(request,'PDF extracted. Review every proposed check before running it. Nothing has been fetched yet.')
            return redirect('review',pk=obj.pk)
        except ValueError as error:form.add_error('pdf',str(error))
    return render(request,'checker/index.html',{'assignments':Assignment.objects.filter(owner=request.user).order_by('-created_at'),'upload_form':form,'ai_ready':ai.configured()},status=400)

@login_required
@require_POST
def demo(request):
    checks=[{'name':'Assignment guide','url':'https://demo.invalid/guide','kind':'http','expected':'','expected_status':200,'page':1,'requires_auth':False},
    {'name':'Sales dataset','url':'https://demo.invalid/sales.csv','kind':'csv','expected':'region,revenue','expected_status':200,'page':1,'requires_auth':False},
    {'name':'Response contract','url':'https://demo.invalid/api','kind':'json','expected':'result','expected_status':200,'page':2,'requires_auth':False},
    {'name':'Submission API','url':'https://demo.invalid/submit','kind':'http','expected':'','expected_status':200,'page':2,'requires_auth':True}]
    obj=Assignment.objects.create(owner=request.user,title='Sales analysis · guided demo',is_demo=True,filename='Built-in fixture (no uploaded PDF)',checks=checks,pages=[{'number':1,'text':'Download sales.csv. Required columns: region, revenue. Calculate totals per region. Review the assignment guide.','links':[]},{'number':2,'text':'The response API must return a top-level result key. The submission endpoint needs credentials.','links':[]}])
    return redirect('review',pk=obj.pk)

@login_required
def review(request,pk):
    obj=get_object_or_404(Assignment,pk=pk,owner=request.user)
    forms=CheckFormSet(request.POST if request.method=='POST' else None,initial=obj.checks)
    if request.method=='POST' and forms.is_valid():
        checks=[{k:v for k,v in row.items() if k!='DELETE'} for row in forms.cleaned_data if row and not row.get('DELETE')]
        if not checks:messages.error(request,'Add at least one complete check.')
        elif any(c['page']>len(obj.pages) for c in checks):messages.error(request,'Source page must exist in the uploaded document.')
        elif request.POST.get('approve')!='yes':messages.error(request,'Confirm you have reviewed and authorized these resource checks.')
        else:
            obj.checks=checks;obj.approved=True;obj.save()
            messages.success(request,'Checks approved. You can now run the Python validations.')
            return redirect('detail',pk=obj.pk)
    return render(request,'checker/review.html',{'assignment':obj,'formset':forms})

@login_required
def detail(request,pk):
    obj=get_object_or_404(Assignment,pk=pk,owner=request.user)
    runs=list(obj.runs.order_by('-created_at'))
    current=runs[0] if runs else None
    if request.GET.get('run'):current=get_object_or_404(Run,pk=request.GET['run'],assignment=obj)
    return render(request,'checker/detail.html',{'assignment':obj,'runs':runs,'current':current,'ai_ready':ai.configured(),'payload':json.dumps(ai.evidence_payload(current),indent=2) if current else ''})

@login_required
@require_POST
def run(request,pk):
    obj=get_object_or_404(Assignment,pk=pk,owner=request.user)
    if not obj.approved:messages.error(request,'Review and approve checks first.');return redirect('review',pk=pk)
    checks=obj.checks
    results=run_all(checks,obj.is_demo)
    Run.objects.create(assignment=obj,results=results,checks_snapshot=checks)
    messages.success(request,'Run complete. Results reflect the recorded check definitions and the time of this run.')
    return redirect('detail',pk=pk)

@login_required
@require_POST
def suggest(request,pk):
    run=get_object_or_404(Run,pk=pk,assignment__owner=request.user)
    if request.POST.get('consent')!='yes':messages.error(request,'Review the evidence and confirm sending it to Groq first.')
    elif not ai.evidence_payload(run):messages.info(request,'No failures or unverified checks need suggestions.')
    else:
        try:run.suggestions=ai.suggest_fixes(ai.evidence_payload(run));run.save(update_fields=['suggestions']);messages.success(request,'AI suggestions added. No resources or checks were changed.')
        except ValueError as error:messages.error(request,str(error))
    return redirect(f'/assignments/{run.assignment_id}/?run={run.pk}')

@login_required
def export(request,pk):
    run=get_object_or_404(Run,pk=pk,assignment__owner=request.user)
    data={'assignment':run.assignment.title,'mode':'demo fixtures' if run.assignment.is_demo else 'live GET checks','run_at':run.created_at.isoformat(),'results':run.results,'ai_suggestions_unverified':run.suggestions}
    response=HttpResponse(json.dumps(data,indent=2),content_type='application/json')
    response['Content-Disposition']='attachment; filename="assignment-health-report.json"'
    return response
