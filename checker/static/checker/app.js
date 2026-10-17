document.querySelectorAll('form[data-busy]').forEach(form=>form.addEventListener('submit',()=>{
  const button=form.querySelector('button[type="submit"], button:not([type])');
  if(button){button.disabled=true;button.textContent=form.dataset.busy;}
}));
const add=document.querySelector('#add-check');
if(add){
  const total=document.querySelector('#id_form-TOTAL_FORMS');
  const update=()=>{add.disabled=Number(total.value)>=8;};update();
  add.addEventListener('click',()=>{const index=Number(total.value);if(index>=8)return;document.querySelector('#check-forms').insertAdjacentHTML('beforeend',document.querySelector('#empty-check').innerHTML.replaceAll('__prefix__',index));total.value=index+1;update();});
}
