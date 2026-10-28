"""Gyroscope rotation notation and analytics rendering."""
import os
import threading
import unittest
from http.server import HTTPServer

from src.server import Handler


@unittest.skipUnless(os.environ.get('RUN_BROWSER_SECURITY_TESTS') == '1', 'Enable Firefox browser tests')
class CubeRotationTests(unittest.TestCase):
    def test_gyro_axes_recording_and_solution_rendering(self):
        from selenium import webdriver
        from selenium.webdriver.firefox.options import Options
        from selenium.webdriver.support.ui import WebDriverWait

        class TestHandler(Handler):
            def do_GET(self):
                if self.path == '/api/timer-scramble':
                    return self.send(200, {'scramble': 'R U'})
                return super().do_GET()

        http = HTTPServer(('127.0.0.1', 0), TestHandler)
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        options = Options()
        options.add_argument('-headless')
        options.binary_location = os.environ.get('FIREFOX_BINARY', '/snap/firefox/current/usr/lib/firefox/firefox')
        try:
            with webdriver.Firefox(options=options) as browser:
                browser.get(f'http://127.0.0.1:{http.server_port}/timer.html')
                WebDriverWait(browser, 10).until(lambda d: d.find_element('id', 'timer-scramble').text == 'R U')
                script = """
                const expect=(value,label)=>{if(!value)throw Error(label);};
                const identity={w:1,x:0,y:0,z:0},c=Math.SQRT1_2;
                for(const [axis,q,face,expected] of [
                    ['x',{w:c,x:-c,y:0,z:0},'U','B'],
                    ['y',{w:c,x:0,y:0,z:-c},'R','F'],
                    ['z',{w:c,x:0,y:c,z:0},'R','D']]){
                    const tracker=new CubeRotationTracker();
                    expect(tracker.orientations.length===24,'24 orientations');
                    tracker.update(identity,0,0);tracker.begin();
                    tracker.update(q,100,1);tracker.update(q,160,1);
                    expect(tracker.events.map(e=>e.move).join(' ')===axis,'gyro axis '+axis);
                    expect(tracker.faceMove(face,170,1)===expected,'remap '+axis);
                }
                const starting=new CubeRotationTracker();
                for(const pose of starting.orientations){
                    const tracker=new CubeRotationTracker(),q=pose.q;
                    tracker.update({w:q.w,x:q.x,y:-q.z,z:q.y},0,0);tracker.begin(100);
                    expect(tracker.events.map(e=>e.move).join(' ')===pose.path.join(' '),'starting pose prefix');
                    expect(CubeRotationTracker.distance(tracker.orientation,q)<.001,'starting pose remapping');
                    expect(tracker.events.every(e=>e.afterMoveIndex===0&&e.ms===0),'initial rotations at zero');
                    tracker.update({w:q.w,x:q.x,y:-q.z,z:q.y},200,1);
                    expect(tracker.events.length===pose.path.length,'no duplicate initial rotations');
                }
                const tilted=new CubeRotationTracker();
                tilted.update({w:c,x:0,y:0,z:-c},0,0);tilted.begin(100);
                const displayMove=tilted.faceMove('R',100,0);
                const initialTrace={trace:{rotations:tilted.timedEvents([{localTimestamp:100}],1000)}};
                expect(SolveAnalytics.solutionMoves(initialTrace,[{move:'R',displayMove,ms:0}]).map(e=>e.move).join(' ')==='y F','initial rotation precedes first remapped turn');
                const noise=new CubeRotationTracker();noise.update(identity,0,0);noise.begin();
                noise.update({w:Math.cos(.05),x:Math.sin(.05),y:0,z:0},100,0);
                noise.update(identity,150,0);expect(!noise.events.length,'jitter must not add rotations');
                const half=new CubeRotationTracker();half.update(identity,0,0);half.begin();
                half.update({w:0,x:0,y:0,z:1},100,1);half.update({w:0,x:0,y:0,z:1},160,1);
                expect(half.events[0].move==='y2','half rotation');
                let record;
                const timer=new BluetoothSolveTimer({finish:result=>{record=result;}},{now:()=>0,later:()=>1,clear(){}});
                timer.configure(true,'R U');
                timer.event({type:'FACELETS',serial:0,facelets:CubeFacelets.apply(CubeFacelets.solved,'R U')});
                timer.event({type:'GYRO',quaternion:identity,timestamp:0});
                timer.event({type:'MOVE',serial:1,move:"U'",cubeTimestamp:1000,localTimestamp:100});
                timer.event({type:'GYRO',quaternion:{w:c,x:0,y:0,z:-c},timestamp:140});
                timer.event({type:'GYRO',quaternion:{w:c,x:0,y:0,z:-c},timestamp:200});
                timer.event({type:'MOVE',serial:2,move:"R'",cubeTimestamp:2000,localTimestamp:1100});
                timer.finish();
                expect(record.ms===1000,'rotation must not change time');
                expect(record.trace.moves.map(item=>item.move).join(' ')==="U' R'",'raw reconstruction preserved');
                expect(record.trace.rotations[0].move==='y','rotation saved');
                expect(record.trace.gyroAvailable,'gyro availability saved');
                record.source='bluetooth';record.scramble='R U';
                const analysis=SolveAnalytics.analyze(record);
                expect(SolveAnalytics.solutionMoves(record,analysis.moves).map(item=>item.move).join(' ')==="U' y F'",'interleaved solution');
                solves.push(record);persist();renderHistory();window.rotationTestPassed=true;
                """
                browser.execute_script("const s=document.createElement('script');s.textContent=arguments[0];document.body.append(s);", script)
                self.assertTrue(browser.execute_script('return window.rotationTestPassed'))
                browser.find_element('css selector', 'button[aria-label="Analytics for solve 1"]').click()
                self.assertEqual(browser.find_element('id', 'analytics-scramble').text, 'R U')
                self.assertEqual([item.text for item in browser.find_elements('css selector', '#analytics-solution span')], ["U'", 'y', "F'"])
                self.assertTrue(browser.find_elements('css selector', '#analytics-solution .analytics-rotation'))
                self.assertTrue(browser.find_elements('css selector', '#analytics-steps .analytics-rotation'))
                self.assertEqual([cell.text for cell in browser.find_elements('css selector', '#analytics-steps .analytics-step-moves') if cell.find_elements('css selector', '.analytics-rotation')], ["y F'"])
                browser.refresh()
                browser.find_element('css selector', 'button[aria-label="Analytics for solve 1"]').click()
                self.assertEqual(browser.find_element('id', 'analytics-scramble').text, 'R U')
                self.assertIn('y', browser.find_element('id', 'analytics-solution').text)
        finally:
            http.shutdown()
            http.server_close()
            thread.join()
