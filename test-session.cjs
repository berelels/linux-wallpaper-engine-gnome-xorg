const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const {EventEmitter}=require('node:events');
const code=fs.readFileSync(path.join(__dirname,'session-main.cjs'),'utf8');
// Each run gets its own fs object so the autostart hook is checked in isolation.
function setup(primary,env={}){const app=new EventEmitter();let loaded=0,quit=0;app.requestSingleInstanceLock=()=>primary;app.quit=()=>quit++;
const window=new EventEmitter();let shown=0,hidden=0,focused=0,restored=0;window.isDestroyed=()=>false;window.isMinimized=()=>true;window.restore=()=>restored++;window.show=()=>shown++;window.hide=()=>hidden++;window.focus=()=>focused++;
const files={...fs};const process={env:{PATH:'/usr/bin',...env}};
const modules={electron:{app,BrowserWindow:{getAllWindows:()=>[window]}},fs:files,os,path};
vm.runInNewContext(code,{process,require:name=>name in modules?modules[name]:loaded++});
return {app,window,files,process,stats:()=>({loaded,quit,shown,hidden,focused,restored})};}
let s=setup(false);assert.equal(s.stats().loaded,0);assert.equal(s.stats().quit,1);
s=setup(true);s.app.emit('browser-window-created',{},s.window);let prevented=0;s.window.emit('close',{preventDefault:()=>prevented++});assert.equal(prevented,1);assert.equal(s.stats().hidden,1);
s.app.emit('second-instance');assert.equal(s.stats().shown,1);assert.equal(s.stats().focused,1);assert.equal(s.stats().restored,1);assert.equal(s.stats().loaded,1);
s.app.emit('before-quit');s.window.emit('close',{preventDefault:()=>prevented++});assert.equal(prevented,1);
// Started directly (as by the browser's own login entry): the GNOME adapter is still found.
const temp=fs.mkdtempSync(path.join(os.tmpdir(),'session test '));
const bin=path.join(temp,'share/wallpaper-engine-gnome/bin');fs.mkdirSync(bin,{recursive:true});fs.writeFileSync(path.join(bin,'linux-wallpaperengine'),'');
s=setup(true,{XDG_DATA_HOME:path.join(temp,'share')});assert.equal(s.process.env.PATH,bin+':/usr/bin');
s=setup(true,{XDG_DATA_HOME:path.join(temp,'missing')});assert.equal(s.process.env.PATH,'/usr/bin');
// The login entry the browser writes starts the integration launcher.
fs.mkdirSync(path.join(temp,'autostart'));const entry=path.join(temp,'autostart/Linux Wallpaper Engine.desktop');
const written='[Desktop Entry]\nComment=Launch Linux Wallpaper Engine on startup\nExec="/opt/browser/linux-wallpaper-engine"\nTerminal=false\n';
s=setup(true,{LWE_LOGIN_EXEC:'"/home/u/run" "/home/u/browser-launcher.py"'});s.files.writeFileSync(entry,written);
assert.match(fs.readFileSync(entry,'utf8'),/^Exec="\/home\/u\/run" "\/home\/u\/browser-launcher.py"$/m);
s.files.writeFileSync(path.join(temp,'other.txt'),written);assert.equal(fs.readFileSync(path.join(temp,'other.txt'),'utf8'),written);
fs.rmSync(temp,{recursive:true});
console.log('PASS: duplicate startup, close-to-hide, reveal same window, explicit quit, adapter PATH, login entry');
