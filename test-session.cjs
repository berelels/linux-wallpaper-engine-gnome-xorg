const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const {EventEmitter}=require('node:events');
const code=fs.readFileSync(require('node:path').join(__dirname,'session-main.cjs'),'utf8');
function setup(primary){const app=new EventEmitter();let loaded=0,quit=0;app.requestSingleInstanceLock=()=>primary;app.quit=()=>quit++;
const window=new EventEmitter();let shown=0,hidden=0,focused=0,restored=0;window.isDestroyed=()=>false;window.isMinimized=()=>true;window.restore=()=>restored++;window.show=()=>shown++;window.hide=()=>hidden++;window.focus=()=>focused++;
vm.runInNewContext(code,{require:name=>name==='electron'?{app,BrowserWindow:{getAllWindows:()=>[window]}}:loaded++});
return {app,window,stats:()=>({loaded,quit,shown,hidden,focused,restored})};}
let s=setup(false);assert.equal(s.stats().loaded,0);assert.equal(s.stats().quit,1);
s=setup(true);s.app.emit('browser-window-created',{},s.window);let prevented=0;s.window.emit('close',{preventDefault:()=>prevented++});assert.equal(prevented,1);assert.equal(s.stats().hidden,1);
s.app.emit('second-instance');assert.equal(s.stats().shown,1);assert.equal(s.stats().focused,1);assert.equal(s.stats().restored,1);assert.equal(s.stats().loaded,1);
s.app.emit('before-quit');s.window.emit('close',{preventDefault:()=>prevented++});assert.equal(prevented,1);
console.log('PASS: duplicate startup, close-to-hide, reveal same window, explicit quit');
