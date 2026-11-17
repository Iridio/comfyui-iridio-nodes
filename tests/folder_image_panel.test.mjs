import assert from 'node:assert/strict';
import { test } from 'node:test';
import { setupFolderImageIterator } from '../web/folder_image_panel.js';

class Element extends EventTarget {
    children=[]; style={}; dataset={}; value=''; hidden=false; disabled=false; attributes={};
    append(...items){for(const item of items){item.remove();item.parent=this;this.children.push(item);}}
    replaceChildren(...items){this.children=[...items];}
    setAttribute(key,value){this.attributes[key]=String(value);}
    click(){if(!this.disabled)this.dispatchEvent(new Event('click'));}
    focus(){}
    remove(){if(this.parent){this.parent.children=this.parent.children.filter(item=>item!==this);this.parent=undefined;}}
}
globalThis.document={createElement:()=>new Element(),head:new Element(),body:new Element(),getElementById:()=>null};

function fixture(names=['1.png','2.png','10.png']){
    document.body=new Element();
    const node={widgets:[{name:'folder',value:'/input'},{name:'selection_json',value:JSON.stringify(names)},
        {name:'next_image',value:1}],properties:{},size:[390,460],
        setDirtyCanvas(){},computeSize(){return [390,460];},setSize(){},
        addDOMWidget(name,type,element,options){this.widgets.push({name,element,options});},};
    const requests=[];
    const api={apiURL:path=>'/proxy'+path,async fetchApi(path){
        requests.push(path);
        assert.ok(path.startsWith('/iridio/folder-images/'));
        const params=new URL('http://host'+path).searchParams;
        const all=names.map(file=>({file,name:file,size:10,mtime_ns:'123'}));
        const offset=Number(params.get('offset')||0),limit=Number(params.get('limit')||200);
        return {ok:true,json:async()=>({folder:'/input',files:all.slice(offset,offset+limit),total:all.length,offset})};
    }};
    setupFolderImageIterator(node,api);
    const elements=()=>{const all=[];const walk=e=>{all.push(e);e.children?.forEach(walk);};walk(node.widgets[3].element);walk(document.body);return all;};
    const button=label=>elements().find(e=>e.textContent===label);
    const serialize=()=>Object.fromEntries(node.widgets.slice(0,3).map(w=>[w.name,w.serializeValue?.()??w.value]));
    return {node,api,button,elements,serialize,names,requests};
}
const tick=()=>new Promise(resolve=>setImmediate(resolve));

test('100 submissions freeze folder/file/index and wrap while execution only updates last used',()=>{
    const {node,serialize}=fixture();
    const graphs=[];
    for(let i=0;i<100;i++){
        const graph=serialize();graphs.push(graph);
        assert.equal(graph.next_image,(i%3)+1);
        node.widgets[2].afterQueued();
    }
    assert.equal(node.widgets[2].value,2);
    node.onExecuted({used_image:[{file:'2.png',index:2,total:3,folder:'/input',path:'/input/2.png'}]});
    assert.equal(node.widgets[2].value,2);
    assert.equal(node.properties.iridioUsedImage.file,'2.png');
    assert.equal(graphs[0].next_image,1);
});

test('failed submission does not consume index and reset during submission wins',()=>{
    const {node,serialize,button}=fixture();
    serialize();serialize();assert.equal(node.widgets[2].value,1);
    node.widgets[2].value=3;serialize();button('Reset to 1').click();node.widgets[2].afterQueued();
    assert.equal(node.widgets[2].value,1);
});

test('serializers share one snapshot despite a selection change and nodes remain independent',()=>{
    const a=fixture(),b=fixture();
    const folder=a.node.widgets[0].serializeValue();
    a.node.widgets[0].value='/other';a.node.widgets[1].value='["new.png"]';a.node.widgets[2].value=9;
    assert.equal(folder,'/input');
    assert.equal(a.node.widgets[1].serializeValue(),'["1.png","2.png","10.png"]');
    assert.equal(a.node.widgets[2].serializeValue(),1);
    a.node.widgets[2].callback();a.node.widgets[2].afterQueued();
    assert.equal(b.node.widgets[2].value,1);
});

test('gallery cancel and refresh use drafts and missing files require a valid confirmed selection',async()=>{
    const {node,button,api,serialize}=fixture();
    button('Select images').click();await tick();
    button('Clear').click();button('Cancel').click();
    assert.equal(serialize().selection_json,'["1.png","2.png","10.png"]');
    node.widgets[2].value=3;
    api.fetchApi=async()=>({ok:true,json:async()=>({folder:'/input',files:[{file:'1.png',name:'1.png',mtime_ns:'1',size:10}],total:1,offset:0})});
    button('Refresh').click();await tick();
    assert.equal(node.widgets[2].value,3);
    assert.equal(button('Apply selection').disabled,true);
    button('Select all').click();await tick();button('Apply selection').click();await tick();
    assert.equal(node.widgets[1].value,'["1.png"]');assert.equal(node.widgets[2].value,1);
});

test('restore does not consume an index or invent last executed state',()=>{
    const {node}=fixture();
    node.widgets[2].value=2;node.onConfigure();
    assert.equal(node.widgets[2].value,2);assert.equal(node.properties.iridioUsedImage,undefined);
});

test('execution notifications preserve an unconfirmed server folder edit',()=>{
    const {node,elements}=fixture();
    const path=elements().find(e=>e.attributes?.['aria-label']==='Server folder');
    path.value='/new/folder/draft';
    node.onExecuted({used_image:[{file:'1.png',index:1,total:3}]});
    assert.equal(path.value,'/new/folder/draft');
    assert.equal(node.widgets[0].value,'/input');
});

test('a late gallery response cannot reopen a cancelled dialog or change selection',async()=>{
    const {node,button,api}=fixture();
    let finish;
    api.fetchApi=()=>new Promise(resolve=>{finish=resolve;});
    button('Select images').click();button('Cancel').click();
    finish({ok:true,json:async()=>({folder:'/input',files:[],total:0,offset:0})});
    await tick();
    assert.equal(document.body.children.length,0);
    assert.equal(node.widgets[1].value,'["1.png","2.png","10.png"]');
});

test('large gallery loads only its visible page before an explicit select all',async()=>{
    const {button,requests}=fixture(Array.from({length:500},(_,i)=>`${i}.png`));
    button('Select images').click();await tick();
    assert.equal(requests.length,1);
    assert.equal(new URL('http://host'+requests[0]).searchParams.get('limit'),'24');
    button('Next page').click();await tick();
    assert.equal(requests.length,2);
    assert.equal(new URL('http://host'+requests[1]).searchParams.get('offset'),'24');
});

test('cancel gallery restores the original visible folder as well as the queued value',async()=>{
    const {node,button,elements,api}=fixture();
    api.fetchApi=async path=>({ok:true,json:async()=>path.includes('/browse') ?
        (path.includes('path=')?{path:'/other',dirs:[],parent:null,total:0}:{path:null,dirs:[{name:'Other',path:'/other'}],total:1}):
        {folder:'/other',files:[{file:'new.png',name:'new.png',mtime_ns:'1',size:10}],total:1,offset:0}});
    button('Browse').click();await tick();button('Other').click();await tick();
    button('Use folder').click();await tick();button('Cancel').click();
    const input=elements().find(e=>e.attributes?.['aria-label']==='Server folder');
    assert.equal(input.value,'/input');assert.equal(node.widgets[0].value,'/input');
});
