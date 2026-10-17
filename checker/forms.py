from django import forms

class UploadForm(forms.Form):
    title=forms.CharField(max_length=160,widget=forms.TextInput(attrs={'placeholder':'e.g. Week 3 · Sales analysis'}))
    pdf=forms.FileField(label='Assignment PDF',widget=forms.ClearableFileInput(attrs={'accept':'.pdf,application/pdf'}))

class CheckForm(forms.Form):
    name=forms.CharField(max_length=120)
    url=forms.URLField(max_length=1000,label='Resource URL',widget=forms.URLInput(attrs={'placeholder':'https://…'}))
    kind=forms.ChoiceField(initial='http',choices=[('http','URL availability'),('csv','CSV structure & columns'),('json','JSON response & keys')],label='Check type')
    expected=forms.CharField(required=False,max_length=500,label='Required columns / top-level JSON keys',help_text='Comma-separated. Leave blank for parsing only. Ignored for URL checks.')
    expected_status=forms.IntegerField(initial=200,min_value=100,max_value=599,label='Expected HTTP status')
    page=forms.IntegerField(initial=1,min_value=1,max_value=30,label='Source page')
    requires_auth=forms.BooleanField(required=False,label='Needs authentication (skip in this version)')

CheckFormSet=forms.formset_factory(CheckForm,extra=1,max_num=8,validate_max=True,can_delete=True)
