from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('node'), 'Node unavailable')
class Html5AudioTests(unittest.TestCase):
    def test_adapter_media_policy_aliases_and_no_flash_options(self):
        script = r'''
const fs=require('fs'), vm=require('vm'), assert=require('assert');
const callbacks=[];
let captured;
const node=()=>({style:{},hidden:false,children:[],setAttribute(){},removeAttribute(){},addEventListener(){},append(...args){for(const child of args){child.parentNode=this;this.children.push(child);}}});
const doc={createElement:node,body:node()};
function $(arg){return arg===doc?{ready:fn=>callbacks.push(fn)}:{off(){},on(){}};}
$.fn={jPlayer:function(options){captured=options;return this;}};
$.jPlayer={event:{error:'jPlayer_error'}};
const ap={init(){},playlist:[]};
const context={window:{jQuery:$,AudioPlayer:ap},document:doc,encodeURIComponent};
vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),context);
const adapter=context.window.NIMBUS_HTML5_AUDIO;
for(const [ext,key] of [['MP3','mp3'],['ogg','oga'],['wave','wav'],['m4a','m4a']]){
 const song={path:'/sdcard/a #?% ü.'+ext,songname:'<fixture>',[ext]:'old'};
 const mapped=adapter.media(song);
 assert.strictEqual(mapped.track[key],'/sdcard/a%20%23%3F%25%20%C3%BC.'+ext);
 assert.strictEqual(song[ext],'old');
}
for(const path of ['https://example.com/a.mp3','javascript:x','//example.com/a.mp3','/storage/../a.mp3','/etc/keys.mp3']){
 assert.throws(()=>adapter.media({path}));
}
const receiver={is:()=>true};
$.fn.jPlayer.call(receiver,{solution:'flash,html',swfPath:'old',wmode:'window',supplied:'ogg,wave'});
assert.strictEqual(captured.solution,'html');
assert.strictEqual(captured.supplied,'mp3,m4a,oga,wav');
assert.ok(!('swfPath' in captured));assert.ok(!('wmode' in captured));
const flashOnlyOptions={solution:'flash'};
$.fn.jPlayer.call({is:()=>false},flashOnlyOptions);
assert.strictEqual(captured,flashOnlyOptions); // Do not alter vendor video or unrelated players.
ap.preventCache({path:'/storage/a.flac'});
assert.strictEqual(doc.body.children[0].children[1].href,'/storage/a.flac');
ap.preventCache({path:'javascript:invalid'});
assert.strictEqual(doc.body.children[0].children[1].hidden,true);
'''
        result = subprocess.run(['node', '-e', script, str(ROOT/'device/unified/audio-html5.js')], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_javascript_syntax(self):
        subprocess.run(['node', '--check', str(ROOT/'device/unified/audio-html5.js')], check=True)
