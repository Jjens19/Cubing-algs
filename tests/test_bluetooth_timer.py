"""Deterministic Bluetooth timing regressions, including cube-state cross-checks.

Run with RUN_BROWSER_SECURITY_TESTS=1 and Firefox/Selenium installed.
"""
import os
import unittest


@unittest.skipUnless(os.environ.get('RUN_BROWSER_SECURITY_TESTS') == '1', 'Enable Firefox browser tests')
class BluetoothTimerTests(unittest.TestCase):
    def test_scramble_timing_and_post_solve_penalties(self):
        from selenium import webdriver
        import json,random,threading
        from http.server import HTTPServer
        from selenium.webdriver.firefox.options import Options
        from selenium.webdriver.support.ui import WebDriverWait
        from src.server import Handler
        from src.scrambler import Cube
        rng=random.Random(4)
        cases=[]
        for _ in range(25):
         algorithm=' '.join(rng.choice('URFDLB')+rng.choice(['',"'",'2']) for _ in range(20))
         cases.append({'algorithm':algorithm,'facelets':Cube().apply(algorithm).normalized()})
        class TestHandler(Handler):
         def do_GET(self):
          if self.path=='/api/timer-scramble':return self.send(200,{'scramble':'R U'})
          return super().do_GET()
        http=HTTPServer(('127.0.0.1',0),TestHandler)
        threading.Thread(target=http.serve_forever,daemon=True).start()
        options=Options();options.add_argument('-headless');options.binary_location=os.environ.get('FIREFOX_BINARY','/snap/firefox/current/usr/lib/firefox/firefox')
        try:
         with webdriver.Firefox(options=options) as d:
          d.get(f'http://127.0.0.1:{http.server_port}/timer.html');wait=WebDriverWait(d,10)
          wait.until(lambda d:d.find_element('id','timer-scramble').text=='R U')
          script='''
          function expect(ok,message){if(!ok)throw Error(message);}
          for(const sample of SAMPLES)expect(CubeFacelets.apply(CubeFacelets.solved,sample.algorithm)===sample.facelets,'Python facelet match');
          function scenario(delta){
            const saved=[],calls=[];let finish;const clock={now:()=>5000,later:fn=>{finish=fn;return 1;},clear(){}};
            const timer=new BluetoothSolveTimer({ready:()=>calls.push('ready'),start:()=>calls.push('start'),stop:r=>calls.push('stop'),finish:r=>saved.push(r)},clock);
            timer.configure(true,'R U');
            timer.event({type:'FACELETS',facelets:CubeFacelets.solved,serial:0});
            timer.event({type:'MOVE',move:'R',serial:1,cubeTimestamp:1000});expect(timer.phase==='waiting','wrong state');
            timer.event({type:'MOVE',move:'U',serial:2,cubeTimestamp:2000});expect(timer.phase==='ready','ready state');
            timer.event({type:'MOVE',move:"U'",serial:3,cubeTimestamp:3000});expect(timer.phase==='running','first move starts');
            // A delayed pre-solve snapshot must not replace the current cube state.
            timer.event({type:'FACELETS',facelets:CubeFacelets.solved,serial:1});expect(timer.phase==='running','stale facelets ignored');
            timer.event({type:'MOVE',move:"R'",serial:4,cubeTimestamp:4500});expect(timer.phase==='settling','solved stops');
            if(delta!==null)timer.event({type:'MOVE',move:'U',serial:5,cubeTimestamp:4500+delta});
            finish();expect(saved.length===1,'saved once');expect(saved[0].ms===1500,'cube timestamps');
            expect(saved[0].penalty===(delta!==null&&delta<=300?'+2':'OK'),'penalty boundary '+delta);
            expect(calls.join(',')==='ready,start,stop','state transitions');
          }
          for(const delta of [null,0,299,300,301,1000])scenario(delta);
  // Resetting or a packet gap must abort a running attempt, never save it.
  const outcomes=[];
  const interrupted=new BluetoothSolveTimer({finish:r=>outcomes.push(r)});
  interrupted.configure(true,'R U');
  interrupted.event({type:'FACELETS',facelets:CubeFacelets.apply(CubeFacelets.solved,'R U'),serial:0});
  interrupted.event({type:'MOVE',move:"U'",serial:1,cubeTimestamp:1000});
  interrupted.reset();expect(interrupted.phase==='waiting'&&outcomes.length===0,'reset aborts');
  interrupted.event({type:'FACELETS',facelets:CubeFacelets.apply(CubeFacelets.solved,'R U'),serial:3});
  interrupted.event({type:'MOVE',move:"U'",serial:5,cubeTimestamp:2000});
  expect(interrupted.phase==='waiting'&&outcomes.length===0,'missed move aborts');
  const paused=new BluetoothSolveTimer();paused.configure(true,'R U');
  paused.event({type:'FACELETS',facelets:CubeFacelets.apply(CubeFacelets.solved,'R U'),serial:0});
  paused.enabled=false;paused.event({type:'MOVE',move:"U'",serial:1});
  paused.enabled=true;paused.event({type:'MOVE',move:"R'",serial:2});
  expect(paused.phase==='waiting','moves in settings cannot start a solve');
  // GAN snapshots may arrive before the corresponding solve moves (including across wraparound).
  for(const initial of [0,254,511]){
    const starts=[],stops=[];
    const streamed=new BluetoothSolveTimer({start:()=>starts.push(true),stop:result=>stops.push(result)});
    streamed.configure(true,'R U');
    streamed.event({type:'FACELETS',facelets:CubeFacelets.apply(CubeFacelets.solved,'R U'),serial:initial});
    streamed.event({type:'FACELETS',facelets:CubeFacelets.apply(CubeFacelets.solved,'R'),serial:initial+1});
    expect(streamed.phase==='ready','ahead snapshot must preserve READY');
    streamed.event({type:'MOVE',move:"U'",serial:initial+1,cubeTimestamp:1000});
    expect(streamed.phase==='running'&&starts.length===1,'first turn remains running');
    streamed.event({type:'FACELETS',facelets:CubeFacelets.solved,serial:initial+2});
    expect(streamed.phase==='running'&&stops.length===0,'ahead solved snapshot must not cancel or stop');
    streamed.event({type:'MOVE',move:"R'",serial:initial+2,cubeTimestamp:2400});
    expect(streamed.phase==='settling'&&stops[0].ms===1400,'stop only on matching solved move');
    streamed.finish();
  }
  const guide=new BluetoothScrambleGuide();guide.configure('R U2 F');
  let seq=0;
  guide.event({type:'FACELETS',facelets:CubeFacelets.solved,serial:seq});
  const turn=move=>guide.event({type:'MOVE',move,serial:++seq});
  turn('R');expect(guide.index===1,'green first move');
  turn('F');turn('L');expect(guide.undo.join(' ')==="L' F'",'inverse wrong moves');
  turn("L'");expect(guide.undo.join(' ')==="F'",'undo shrinks');
  turn("F'");expect(guide.index===1&&guide.undo.length===0,'progress restored');
  turn('U');expect(guide.index===1&&guide.undo.length===0,'partial half turn');
  turn('F');expect(guide.undo.join(' ')==="F' U'",'undo partial half and mistake');
  turn("F'");turn("U'");expect(guide.index===1&&guide.undo.length===0,'partial error restored');
  turn("U'");turn("U'");expect(guide.index===2,'two opposite quarters complete half turn');
  turn('F');expect(guide.index===3,'full scramble complete');
  turn('R');expect(guide.undo.length===0,'solve moves do not trigger undo');
  const recovered=BluetoothMoveTiming.fromMoves([
    {move:'R',cubeTimestamp:1000,localTimestamp:100,receivedTimestamp:100},
    {move:'U',cubeTimestamp:null,localTimestamp:null,receivedTimestamp:9999},
    {move:"U'",cubeTimestamp:1200,localTimestamp:300,receivedTimestamp:300},
    {move:"R'",cubeTimestamp:2000,localTimestamp:1100,receivedTimestamp:1100}
  ]);
  expect(recovered.ms===1000&&recovered.moves.map(move=>move.ms).join(',')==='0,100,200,1000','recovered moves use one cube timeline');
  expect(recovered.estimated,'recovered timestamps marked estimated');
  const wrapped=BluetoothMoveTiming.fromMoves([
    {move:'R',cubeTimestamp:0xfffffff0,localTimestamp:0,receivedTimestamp:0},
    {move:"R'",cubeTimestamp:16,localTimestamp:32,receivedTimestamp:32}
  ]);
  expect(wrapped.ms===32,'cube clock rollover');
  const host=BluetoothMoveTiming.fromMoves([
    {move:'R',cubeTimestamp:null,localTimestamp:1000,receivedTimestamp:1000},
    {move:'U',cubeTimestamp:null,localTimestamp:null,receivedTimestamp:9999},
    {move:"R'",cubeTimestamp:null,localTimestamp:1500,receivedTimestamp:1500}
  ]);
  expect(host.ms===500&&host.moves[1].ms===250,'host-only timeline interpolates recovered packets');
          window.pureTimingPassed=true;
          '''.replace('SAMPLES',json.dumps(cases))
          d.execute_script("const s=document.createElement('script');s.textContent=arguments[0];document.body.append(s);",script)
          assert d.execute_script('return window.pureTimingPassed')
          d.execute_script("document.dispatchEvent(new CustomEvent('bluetooth-cube-connected'));")
          assert d.find_element('id','timer-mode').get_attribute('value')=='bluetooth'
          def event(value):d.execute_script("document.dispatchEvent(new CustomEvent('bluetooth-cube-event',{detail:arguments[0]}));",value)
          event({'type':'FACELETS','facelets':Cube().normalized(),'serial':0})
          event({'type':'MOVE','move':'R','serial':1,'cubeTimestamp':1000})
          assert len(d.find_elements('css selector','#timer-scramble .scramble-done'))==1
          event({'type':'MOVE','move':'F','serial':2,'cubeTimestamp':1500})
          assert d.find_element('css selector','#timer-scramble .scramble-undo').text=="F'"
          event({'type':'MOVE','move':"F'",'serial':3,'cubeTimestamp':1600})
          assert not d.find_elements('css selector','#timer-scramble .scramble-undo')
          assert len(d.find_elements('css selector','#timer-scramble .scramble-done'))==1
          event({'type':'MOVE','move':'U','serial':4,'cubeTimestamp':2000})
          assert d.find_element('id','timer-clock').text=='READY'
          event({'type':'MOVE','move':"U'",'serial':5,'cubeTimestamp':3000})
          assert not d.find_element('id','timer-session').is_enabled()
          event({'type':'MOVE','move':"R'",'serial':6,'cubeTimestamp':4500})
          event({'type':'MOVE','move':'U','serial':7,'cubeTimestamp':4700})
          wait.until(lambda d:d.find_element('id','stat-count').text=='1')
          assert d.find_element('css selector','#solve-list td:nth-child(2)').text=='3.50+'
          assert d.find_element('css selector','#solve-list select').get_attribute('value')=='+2'
          assert not d.find_element('id','solve-analytics').is_displayed()
          d.find_element('css selector','button[aria-label="Analytics for solve 1"]').click()
          assert [move.text for move in d.find_elements('css selector','#analytics-solution span')]==["U'","R'"]
          event({'type':'MOVE','move':'R','serial':8,'cubeTimestamp':5500})
          assert not d.find_element('id','solve-analytics').is_displayed()
          d.find_element('css selector','button[aria-label="Analytics for solve 1"]').click()
          assert d.find_element('id','solve-analytics').is_displayed()
          event({'type':'FACELETS','facelets':Cube().apply('R U').normalized(),'serial':8})
          event({'type':'MOVE','move':"U'",'serial':9,'cubeTimestamp':6000})
          event({'type':'MOVE','move':"R'",'serial':10,'cubeTimestamp':7500})
          wait.until(lambda d:d.find_element('id','stat-count').text=='2')
          assert d.find_element('id','solve-analytics').is_displayed()
          d.execute_script("document.dispatchEvent(new CustomEvent('bluetooth-cube-disconnected'));")
          assert d.find_element('id','timer-mode').get_attribute('value')=='click'
          print('PASS: 25 facelet simulations match Python; scramble matching, READY, first-move start, solved stop, cube timestamps, stale snapshots, +2 boundaries, session save and disconnect.')
        finally:http.shutdown();http.server_close()
