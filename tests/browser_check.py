#!/usr/bin/env python3
"""Write a self-contained Chrome smoke test for the dashboard."""
import argparse
from pathlib import Path

MOCK = """
<script>
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
const response = value => new Response(JSON.stringify(value));
const pending = id => ({inspection_id:id, created_at:new Date().toISOString(),
  source:'upload', classification:'normal', screening_decision:'PASS',
  required_action:'STANDARD_QC_REVIEW', probability_defective:.1, llama_status:'PENDING'});
const finished = id => ({...pending(id), classification:'defective', screening_decision:'FAIL',
  required_action:'QUARANTINE', advisory_check_id:2, advisory_source:'rule_fallback',
  advisory_check_text:'Approved reinspection', llama_status:'FALLBACK', vision_forward_ms:300,
  verdict_wall_s:1.4, llama_queue_s:.1, llama_latency_s:17});
let posts = 0, oldPoll = false, releaseOld;
window.fetch = async (url, options) => {
  if(url==='/api/system')return response({network_up:true, cpu_architecture:'test'});
  if(url.startsWith('/api/stats?'))return response({passed:65,failed:2});
  if(url==='/api/history')return response([finished('new')]);
  if(url==='/api/inspect'){
    posts++;
    const body=JSON.parse(options.body);
    if(body.source!=='upload'||body.pill_present_confirmed!==true||
       !body.image.startsWith('data:image/png;base64,'))throw Error('wrong mobile upload request');
    await wait(80);
    return response(posts===1 ? pending('old') : finished('new'));
  }
  if(url==='/api/inspection/old'){
    oldPoll=true;
    return new Promise(resolve=>{releaseOld=()=>resolve(response({...pending('old'),llama_status:'COMPLETED'}))});
  }
  if(url==='/api/inspection/new')return response(finished('new'));
  if(url==='/api/inspection/unknown')return response({...finished('unknown'),screening_decision:'INVALID'});
  throw Error(url);
};
</script>
"""

CHECK = """
<script>
(async()=>{
  const assert=(ok,name)=>{if(!ok)throw Error(name)};
  const until=async (callback,name)=>{
    for(let i=0;i<60;i++){
      if(callback())return;
      await wait(50);
    }
    throw Error(name);
  };
  try{
    assert(innerWidth<=850,'mobile width');
    for(const id of ['imagefile','videofile']){
      const picker=$(id);
      picker.focus();
      assert(document.activeElement===picker && picker.tabIndex===0,id+' keyboard focus');
      assert(picker.labels.length===1,id+' accessible label');
      assert(getComputedStyle(picker.labels[0]).outlineStyle==='solid',id+' visible focus');
    }
    await until(()=>$('today').textContent==='67','full-day counts');
    assert($('device').textContent.includes('Network interface up'),'interface label');
    // A real one-pixel PNG; Chrome must decode it for the preview.
    const png='iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+W7ZsAAAAASUVORK5CYII=';
    const file=new File([Uint8Array.from(atob(png),byte=>byte.charCodeAt(0))],
      'upload.png',{type:'image/png'});
    const transfer=new DataTransfer();
    transfer.items.add(file);
    $('imagefile').files=transfer.files;
    $('imagefile').dispatchEvent(new Event('change'));
    await until(()=>$('preview').naturalWidth===1,'decoded image preview');
    assert($('inspectBtn').disabled,'operator confirmation required');
    $('pillConfirmed').click();
    const first=$('inspectBtn').onclick();
    assert($('inspectBtn').disabled,'active submission guard');
    $('pillConfirmed').click();
    $('pillConfirmed').click();
    await $('inspectBtn').onclick();
    await first;
    assert(posts===1,'duplicate submission');
    await until(()=>oldPoll,'old advisory request');
    await $('inspectBtn').onclick();
    assert($('verdict').textContent==='FAIL','new FAIL verdict');
    const marker=document.querySelector('.threshold');
    assert(getComputedStyle(marker,'::after').content==='none','overlapping threshold label');
    assert(document.querySelector('.scorehead').textContent.includes('threshold 0.30'),
           'threshold remains readable');
    assert(document.documentElement.scrollWidth===document.documentElement.clientWidth,'mobile page overflow');
    assert($('llama').textContent.includes('Rule fallback'),'advisory provenance');
    releaseOld();
    await wait(100);
    assert($('verdict').textContent==='FAIL','stale poll overwrote newer verdict');
    assert($('timeline').textContent.includes('Advisory queue'),'advisory timing');
    await selectHistory('unknown');
    assert($('verdict').textContent==='UNKNOWN','invalid result rendered as PASS');
    assert(!$('action').textContent.includes('Continue'),'invalid QC action');
    assert($('llama').textContent.startsWith('Advisory unavailable'),'invalid result advisory');
    render({...finished('legacy'),advisory_check_id:1,advisory_check_text:'Unsafe legacy advice'});
    assert(!$('llama').textContent.includes('Unsafe legacy advice'),'unsafe legacy FAIL advisory');
    document.body.dataset.browserCheck='PASS';
  }catch(error){
    document.body.dataset.browserCheck='FAIL '+error.message;
  }
})();
</script>
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    html = (Path(__file__).resolve().parents[1] / "app/index.html").read_text()
    args.out.write_text(html.replace("<script>", MOCK + "<script>", 1)
                        .replace("</body>", CHECK + "</body>"), encoding="utf-8")


if __name__ == "__main__":
    main()
