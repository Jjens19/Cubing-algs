"""Method reconstruction and historical Bluetooth solve analytics."""
import os
import unittest


@unittest.skipUnless(os.environ.get('RUN_BROWSER_SECURITY_TESTS') == '1', 'Enable Firefox browser tests')
class SolveAnalyticsTests(unittest.TestCase):
    def test_method_splits_history_replay_and_persistence(self):
        from selenium import webdriver
        import json,threading
        from http.server import HTTPServer
        from selenium.webdriver.firefox.options import Options
        from selenium.webdriver.support.ui import WebDriverWait
        from src.server import Handler
        from src.scrambler import Cube,invert
        algorithms={
         'CFOP':"F2 R U R' F R U R' U' F' R U R' U' R' F R2 U' R' U' R U R' F'",
         'CFCE':"F2 R U R' R U R' U R U2 R' M' U M U2 M' U M",
         'Roux':"L' U' L R U R' R U R' U R U2 R' M U2 M'",
        }
        # Express slice turns as outer turns while carrying cube rotations to the end.
        def outer_turns(algorithm):
         expanded=[]
         for move in algorithm.split():
          if move[0]=='M':
           expanded.extend({'M':"x' R L'", "M'":"x R' L", 'M2':'x2 R2 L2'}[move].split())
          else:expanded.append(move)
         unique=''.join(chr(0x100+i) for i in range(54));orientation=[];result=[]
         for move in expanded:
          if move[0] in 'xyz':orientation.append(move);continue
          left=Cube(unique).apply(' '.join(orientation+[move])).facelets
          candidates=[face+suffix for face in 'URFDLB' for suffix in ['',"'",'2']]
          match=next(candidate for candidate in candidates if Cube(unique).apply(' '.join([candidate]+orientation)).facelets==left)
          result.append(match)
         return ' '.join(result)
        algorithms={name:outer_turns(algorithm) for name,algorithm in algorithms.items()}
        fixtures={name:{'ms':(len(algorithm.split())-1)*100,'source':'bluetooth','penalty':'OK','scramble':invert(algorithm),'trace':{'initialFacelets':Cube().apply(invert(algorithm)).normalized(),'moves':[{'move':move,'ms':i*100} for i,move in enumerate(algorithm.split())]}} for name,algorithm in algorithms.items()}
        class TestHandler(Handler):
         def do_GET(self):
          if self.path=='/api/timer-scramble':return self.send(200,{'scramble':'R U'})
          return super().do_GET()
        http=HTTPServer(('127.0.0.1',0),TestHandler)
        threading.Thread(target=http.serve_forever,daemon=True).start()
        options=Options();options.add_argument('-headless');options.binary_location=os.environ.get('FIREFOX_BINARY','/snap/firefox/current/usr/lib/firefox/firefox')
        try:
         with webdriver.Firefox(options=options) as d:
          d.get(f'http://127.0.0.1:{http.server_port}/timer.html');WebDriverWait(d,10).until(lambda d:d.find_element('id','timer-scramble').text=='R U')
          script='''
          const fixtures=FIXTURES;window.analyticsResults={};
          for(const [name,solve] of Object.entries(fixtures)){
            const analysis=SolveAnalytics.analyze(solve);window.analyticsResults[name]=analysis;
            if(analysis.method!==name)throw Error(name+' detected as '+analysis.method);
            const leaves=analysis.rows.filter(row=>!row.group);
            if(Math.abs(leaves.reduce((sum,row)=>sum+row.ms,0)-solve.ms)>1)throw Error('Duration total '+name);
            if(name!=='Roux'&&analysis.rows.filter(row=>row.child).length!==4)throw Error('F2L pairs missing');
          }
          for(const solve of [{ms:1000,source:'bluetooth',penalty:'OK'},
            {...fixtures.CFOP,trace:{...fixtures.CFOP.trace,moves:fixtures.CFOP.trace.moves.slice(0,-1)}},
            {...fixtures.CFOP,trace:{...fixtures.CFOP.trace,moves:[{move:'?',ms:0}]}}]){
            solve.analyticsMethod='CFCE';
            const result=SolveAnalytics.analyze(solve);
            if(result.method!=='CFCE'||!result.note.includes('selected manually'))throw Error('Manual override ignored on incomplete trace');
          }
          const broken=JSON.parse(JSON.stringify(fixtures.CFOP));
          broken.trace.moves[2].ms=broken.ms+1000;
          broken.trace.moves[5].ms=broken.trace.moves[4].ms-100;
          const original=JSON.stringify(broken),repaired=SolveAnalytics.analyze(broken);
          if(repaired.moves.length!==broken.trace.moves.length||!repaired.rows.length||!repaired.timingEstimated)throw Error('Historical timing repair lost moves or splits');
          if(JSON.stringify(broken)!==original)throw Error('Analytics changed the stored recording');
          window.brokenAnalyticsFixture=broken;
          const grouped=(moves,times)=>SolveAnalytics.groupMoves(moves.split(' ').map((move,i)=>({move,ms:times[i]}))).map(item=>item.move).join(' ');
          if(grouped('U U',[0,200])!=='U2')throw Error('200ms inclusive');
          if(grouped('U U',[0,201])!=='U U')throw Error('pause must split');
          if(grouped('U U U',[0,150,300])!=='U3')throw Error('triple grouping');
          if(grouped("U U'",[0,10])!=="U U'")throw Error('opposite moves must stay separate');
          if(grouped("U' U' U'",[0,100,200])!=="U3'")throw Error('inverse triples');
          if(grouped('U U R R U U',[0,100,150,200,250,500])!=='U2 R2 U U')throw Error('consecutive groups only');
          if(grouped('U U',[null,null])!=='U U')throw Error('missing timing must not group');
          window.analyticsFixtures=fixtures;window.analyticsPassed=true;
          '''.replace('FIXTURES',json.dumps(fixtures))
          d.execute_script("const s=document.createElement('script');s.textContent=arguments[0];document.body.append(s);",script)
          assert {name:result['method'] for name,result in d.execute_script('return window.analyticsResults').items()}=={name:name for name in fixtures}
          assert d.execute_script('return window.analyticsPassed')
          assert set(d.execute_script('return Object.keys(window.analyticsResults)'))==set(fixtures)
          d.execute_script("const s=document.createElement('script');s.textContent='solves.push(...Object.values(window.analyticsFixtures));persist();renderHistory();';document.body.append(s);")
          for index,name in enumerate(fixtures,1):
           d.find_element('css selector',f'button[aria-label="Analytics for solve {index}"]').click()
           assert name in d.find_element('id','analytics-summary').text
           assert d.find_element('id','analytics-solution').text
          d.refresh()
          d.find_element('css selector','button[aria-label="Analytics for solve 1"]').click()
          assert 'CFOP' in d.find_element('id','analytics-summary').text
          from selenium.webdriver.support.ui import Select
          Select(d.find_element('id','analytics-method')).select_by_value('CFCE')
          assert 'CFCE' in d.find_element('id','analytics-summary').text
          assert 'CLL' in d.find_element('id','analytics-steps').text
          assert 'selected manually' in d.find_element('id','analytics-method-note').text
          d.find_element('css selector','button[aria-label="Analytics for solve 2"]').click()
          assert Select(d.find_element('id','analytics-method')).first_selected_option.get_attribute('value')=='auto'
          d.refresh()
          d.find_element('css selector','button[aria-label="Analytics for solve 1"]').click()
          assert Select(d.find_element('id','analytics-method')).first_selected_option.get_attribute('value')=='CFCE'
          Select(d.find_element('id','analytics-method')).select_by_value('Roux')
          assert 'CMLL' in d.find_element('id','analytics-steps').text
          Select(d.find_element('id','analytics-method')).select_by_value('auto')
          assert 'CFOP' in d.find_element('id','analytics-summary').text
          assert 'OLL' in d.find_element('id','analytics-steps').text
          # Older solves lack traces: method selection must still save and visibly change.
          d.execute_script("const s=document.createElement('script');s.textContent=arguments[0];document.body.append(s);", "solves.push({ms:1000,penalty:'OK',source:'bluetooth',scramble:'R U'});persist();renderHistory();")
          d.find_element('css selector','button[aria-label="Analytics for solve 4"]').click()
          Select(d.find_element('id','analytics-method')).select_by_value('CFCE')
          assert 'CFCE' in d.find_element('id','analytics-summary').text
          assert 'Using CFCE' in d.find_element('id','analytics-selection-status').text
          assert 'no recorded move history' in d.find_element('id','analytics-method-note').text
          d.execute_script("const s=document.createElement('script');s.textContent=arguments[0];document.body.append(s);", "const broken=JSON.parse(JSON.stringify(solves[0]));broken.trace.moves[2].ms=broken.ms+1000;solves.push(broken);persist();renderHistory();")
          d.find_element('css selector','button[aria-label="Analytics for solve 5"]').click()
          assert len(d.find_elements('css selector','#analytics-solution span'))==len(fixtures['CFOP']['trace']['moves'])
          assert 'interpolated' in d.find_element('id','analytics-method-note').text
          assert d.find_elements('css selector','#analytics-steps tr')
          d.set_window_size(390,1000)
          assert d.execute_script('return document.documentElement.scrollWidth<=innerWidth')

        finally:http.shutdown();http.server_close()
