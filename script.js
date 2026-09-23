const menu=document.querySelector('.menu-toggle');const nav=document.querySelector('.nav');if(menu){menu.addEventListener('click',()=>{const open=nav.classList.toggle('open');menu.setAttribute('aria-expanded',open)})}document.querySelectorAll('.nav a').forEach(a=>a.addEventListener('click',()=>nav.classList.remove('open')));
async function submitForm(form,type){const status=form.querySelector('.form-status');const button=form.querySelector('button[type="submit"]');status.textContent='Submitting…';button.disabled=true;try{const data=Object.fromEntries(new FormData(form).entries());const r=await fetch('/api/submit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({type,data})});const out=await r.json();if(!r.ok)throw new Error(out.error||'Submission failed');if(type!=='Sponsor / Donor Interest')form.reset();status.textContent=`Thank you. Your ${type.toLowerCase()} was received. Reference: ${out.reference}.`;status.style.color='#0B1F3A';if(type==='Sponsor / Donor Interest'){const support=form.querySelector('[name="support"]')?.value||'';const payable=['Donation','Financial sponsorship','Training sponsorship'].includes(support);const options=form.querySelector('.sponsor-payment-options');if(options){options.classList.toggle('is-visible',payable);if(payable)setTimeout(()=>options.scrollIntoView({behavior:'smooth',block:'nearest'}),150);}}}catch(e){status.textContent='We could not submit your information. Please try again.';status.style.color='#9b2c2c';}finally{button.disabled=false}}
document.querySelectorAll('form[data-type]').forEach(form=>form.addEventListener('submit',e=>{e.preventDefault();submitForm(form,form.dataset.type)}));
const cf=document.querySelector('#contact-form');if(cf)cf.addEventListener('submit',e=>{e.preventDefault();submitForm(cf,'Contact Message')});

function animateImpactCounters(){const counters=document.querySelectorAll('.impact-counter');if(!counters.length)return;const duration=1800;const start=performance.now();const tick=now=>{const progress=Math.min((now-start)/duration,1);counters.forEach((el,index)=>{if(progress<1){const value=Math.floor((1-Math.pow(1-progress,3))*(18+index*11));el.textContent=String(value).padStart(2,'0');}else{el.textContent=el.dataset.final||'Growing';}});if(progress<1)requestAnimationFrame(tick)};requestAnimationFrame(tick)}
const impact=document.querySelector('.impact');if(impact){const observer=new IntersectionObserver(entries=>{if(entries.some(entry=>entry.isIntersecting)){animateImpactCounters();observer.disconnect()}},{threshold:.25});observer.observe(impact)}

/* Keep the primary navigation in sync with clicks and the section currently on screen. */
const navLinks=[...document.querySelectorAll('.nav a[href^="#"]')];
const navSections=navLinks.map(link=>{
  const id=link.getAttribute('href').slice(1);
  const section=document.getElementById(id);
  return section?{link,section}:null;
}).filter(Boolean);

function setActiveNav(link){
  navLinks.forEach(item=>{
    const active=item===link;
    item.classList.toggle('active',active);
    if(active)item.setAttribute('aria-current','page');
    else item.removeAttribute('aria-current');
  });
}

let clickedNavTarget=null;

if(navSections.length){
  const navObserver=new IntersectionObserver(entries=>{
    const visible=entries
      .filter(entry=>entry.isIntersecting)
      .sort((a,b)=>b.intersectionRatio-a.intersectionRatio);

    if(clickedNavTarget){
      const targetEntry=entries.find(entry=>entry.target===clickedNavTarget.section && entry.isIntersecting);
      if(targetEntry){
        setActiveNav(clickedNavTarget.link);
        clickedNavTarget=null;
      }
      return;
    }

    if(visible.length){
      const match=navSections.find(item=>item.section===visible[0].target);
      if(match)setActiveNav(match.link);
    }
  },{
    root:null,
    rootMargin:'-25% 0px -55% 0px',
    threshold:[0,.15,.35,.6]
  });

  navSections.forEach(item=>navObserver.observe(item.section));

  navLinks.forEach(link=>{
    link.addEventListener('click',()=>{
      const match=navSections.find(item=>item.link===link);
      if(match){
        clickedNavTarget=match;
        setActiveNav(link);
      }
    });
  });
}


/* Accessibility controller — supports all display options and keeps old settings compatible. */
(function(){
  const toggle=document.querySelector('.accessibility-toggle');
  const panel=document.querySelector('#accessibility-panel');
  const close=document.querySelector('.accessibility-close');
  const controls=[...document.querySelectorAll('[data-a11y]')];
  if(!toggle||!panel)return;
  const storageKey='focusclub-accessibility';
  const defaults={larger:false,contrast:false,underline:false,reduce:false,spacing:false,grayscale:false,cursor:false,focus:false};
  let state={...defaults};
  try{
    const saved=JSON.parse(localStorage.getItem(storageKey)||'{}');
    if(saved&&typeof saved==='object')state={...state,...saved};
  }catch(e){}
  const classMap={
    larger:'a11y-larger-text',contrast:'a11y-high-contrast',underline:'a11y-underline-links',
    reduce:'a11y-reduce-motion',spacing:'a11y-text-spacing',grayscale:'a11y-grayscale',
    cursor:'a11y-large-cursor',focus:'a11y-focus-highlight'
  };
  const keyForButton={
    'text-larger':'larger','high-contrast':'contrast','underline-links':'underline',
    'reduce-motion':'reduce','text-spacing':'spacing','grayscale':'grayscale',
    'large-cursor':'cursor','focus-highlight':'focus'
  };
  function apply(){
    Object.entries(classMap).forEach(([key,cls])=>document.body.classList.toggle(cls,!!state[key]));
    controls.forEach(btn=>{
      const key=keyForButton[btn.dataset.a11y];
      if(key){
        btn.dataset.active=String(!!state[key]);
        btn.setAttribute('aria-pressed',String(!!state[key]));
      }else if(btn.dataset.a11y==='reset'){
        btn.dataset.active='false';
      }
    });
    try{localStorage.setItem(storageKey,JSON.stringify(state))}catch(e){}
  }
  function openPanel(){panel.hidden=false;toggle.setAttribute('aria-expanded','true');}
  function closePanel(){panel.hidden=true;toggle.setAttribute('aria-expanded','false');toggle.focus();}
  toggle.addEventListener('click',()=>panel.hidden?openPanel():closePanel());
  close?.addEventListener('click',closePanel);
  controls.forEach(btn=>btn.addEventListener('click',()=>{
    const action=btn.dataset.a11y;
    if(action==='reset') state={...defaults};
    else {
      const key=keyForButton[action];
      if(key) state[key]=!state[key];
    }
    apply();
  }));
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!panel.hidden)closePanel()});
  apply();
})();
