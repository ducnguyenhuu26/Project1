// @vitest-environment jsdom
import { useState } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import type { Detection, Material, Scan } from '../types';

vi.mock('../lib/useReveal', () => ({ useReveal: () => ({ current: null }) }));
vi.mock('../lib/language', () => ({ useLanguage: () => ({ t: (viText: string) => viText }) }));
vi.mock('./RecommendationWizard', () => ({ RecommendationWizard: ({ session, onSessionChange, categoryId, source }: any) => <div data-testid="wizard">
  <span>{categoryId}:{source}:{session.confirmedObjectId}:{session.answers.condition}:{session.recommendation?.headline}</span>
  <button onClick={() => onSessionChange({ confirmedObjectId: 'plastic_bottle', answers: { condition: 'clean' }, recommendation: { status: 'complete', headline: 'Bottle advice' } })}>Complete item</button>
  <button onClick={() => onSessionChange({...session,answers:{condition:'damaged'},recommendation:null})}>Change answer</button>
</div> }));
import { ScanStudio } from './ScanStudio';

const materials: Material[] = ['plastic', 'textile', 'paper'].map(id => ({ id, name: id, ai_class: null, examples: [], do: [], avoid: [], caution: '', description: '', vn_tip: '' }));
const detection = (id: string, category_id: string): Detection => ({ id, class_id: 0, category_id, label: category_id, material_id: category_id, confidence: .8, bbox_xyxy: [10, 10, 80, 80], origin: 'ai', status: 'detected', model_version: 'yolo26s' });
const scan = (detections: Detection[]): Scan => ({ mode: 'real', model_version: 'yolo26s', taxonomy_version: '1', supported_category_ids: ['plastic'], image_width: 200, image_height: 200, detections, summary: [], advice: [], warnings: [] });
function Harness({detections, initial = 'det-a', mode = 'real', scanId = 'scan-1', onRegion = () => {}}: { detections: Detection[]; initial?: string; mode?: string; scanId?: string; onRegion?: (box:[number,number,number,number])=>void }) {
  const [selected, setSelected] = useState<string | null>(initial);
  const [corrections, setCorrections] = useState<Record<string,string>>({});
  const [excluded, setExcluded] = useState<string[]>([]);
  return <ScanStudio file={null} preview="image.png" scan={{...scan(detections),mode}} scanContextKey={scanId} materials={materials} supportedIds={['plastic']} busy={false} error="" regionBusy={false} regionError="" onRegion={onRegion} onChoose={() => {}} onAnalyze={() => {}} onDemo={() => {}} onCorrect={(d,id) => {setCorrections(p => ({...p,[d.id]:id}));setSelected(d.id);}} onExclude={id => {setExcluded(p => [...p,id]);setSelected('manual');}} onSelect={setSelected} selected={selected} onManual={() => setSelected('manual')} active={[]} manual={[]} corrections={corrections} excluded={excluded}/>;
}
afterEach(cleanup);
describe('per detection scan flow', () => {
  it('selects two identical classes independently by card and keyboard box', () => {
    render(<Harness detections={[detection('det-a','plastic'), detection('det-b','plastic')]}/>);
    fireEvent.click(screen.getByText('Complete item'));
    expect(screen.getByTestId('wizard').textContent).toContain('Bottle advice');
    fireEvent.click(screen.getByRole('button', {name:'Chọn vật thể 2: plastic'}));
    expect(screen.getByTestId('wizard').textContent).not.toContain('Bottle advice');
    fireEvent.keyDown(screen.getByRole('button', {name:'plastic, vật thể 1'}), {key:'Enter'});
    expect(screen.getByTestId('wizard').textContent).toContain('Bottle advice');
  });
  it('corrects and excludes only the target detection', () => {
    render(<Harness detections={[detection('det-a','textile'), detection('det-b','plastic')]}/>);
    fireEvent.change(screen.getByLabelText('Sửa nhãn vật thể 1'), {target:{value:'paper'}});
    expect(screen.getByTestId('wizard').textContent).toContain('paper:corrected');
    fireEvent.click(screen.getByRole('button', {name:'Chọn vật thể 2: plastic'}));
    expect(screen.getByTestId('wizard').textContent).toContain('plastic:detected');
    fireEvent.click(screen.getByLabelText('Loại bỏ vật thể 2'));
    expect(screen.queryByRole('button', {name:'Chọn vật thể 2: plastic'})).toBeNull();
  });
  it('opens manual lookup with zero detections', () => {
    render(<Harness detections={[]} initial="manual"/>);
    expect(screen.getByTestId('wizard').textContent).toContain(':manual:');
    expect(screen.getByText('Không tìm thấy / tra cứu toàn bộ')).toBeTruthy();
  });
  it('invalidates only the changed item and keeps demo visibly illustrative', () => {
    render(<Harness detections={[detection('det-a','plastic'),detection('det-b','plastic')]} mode="demo"/>);
    expect(screen.getAllByText(/DEMO · ẢNH MẪU|ẢNH MẪU · DEMO/).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByText('Complete item'));
    fireEvent.click(screen.getByRole('button',{name:'Chọn vật thể 2: plastic'}));
    fireEvent.click(screen.getByText('Complete item'));
    fireEvent.click(screen.getByText('Change answer'));
    expect(screen.getByTestId('wizard').textContent).not.toContain('Bottle advice');
    fireEvent.click(screen.getByRole('button',{name:'Chọn vật thể 1: plastic'}));
    expect(screen.getByTestId('wizard').textContent).toContain('Bottle advice');
  });
  it('never carries a completed item into a new scan with reused detection IDs', () => {
    const detections=[detection('det-a','plastic')];
    const view=render(<Harness detections={detections}/>);
    fireEvent.click(screen.getByText('Complete item'));
    expect(screen.getByTestId('wizard').textContent).toContain('Bottle advice');
    view.rerender(<Harness detections={detections} scanId="scan-2"/>);
    expect(screen.getByTestId('wizard').textContent).not.toContain('Bottle advice');
  });
  it('keeps the manual session scoped to the current scan',()=>{
    const view=render(<Harness detections={[]} initial="manual" scanId="scan-1"/>);
    fireEvent.click(screen.getByText('Complete item'));
    expect(screen.getByTestId('wizard').textContent).toContain('Bottle advice');
    view.rerender(<Harness detections={[]} initial="manual" scanId="scan-2"/>);
    expect(screen.getByTestId('wizard').textContent).not.toContain('Bottle advice');
  });
  it('shows the corrected class while retaining the original YOLO label',()=>{
    render(<Harness detections={[detection('det-a','textile')]}/>);
    fireEvent.change(screen.getByLabelText('Sửa nhãn vật thể 1'),{target:{value:'paper'}});
    expect(screen.getByRole('button',{name:'Chọn vật thể 1: paper'})).toBeTruthy();
    expect(screen.getByText('paper')).toBeTruthy();
    expect(screen.getByText('Đã sửa nhãn · YOLO gợi ý: textile')).toBeTruthy();
  });
  it('submits the exact drawn image region for a second detection pass', () => {
    const onRegion=vi.fn();
    render(<Harness detections={[]} initial="manual" onRegion={onRegion}/>);
    fireEvent.click(screen.getByText('Khoanh vật thể bị bỏ sót'));
    const overlay=screen.getByRole('img',{name:'Kéo để khoanh vùng vật thể bị bỏ sót'});
    vi.spyOn(overlay,'getBoundingClientRect').mockReturnValue({left:0,top:0,width:200,height:200} as DOMRect);
    fireEvent.pointerDown(overlay,{clientX:20,clientY:30,pointerId:1});
    fireEvent.pointerMove(overlay,{clientX:100,clientY:130,pointerId:1});
    fireEvent.pointerUp(overlay,{clientX:100,clientY:130,pointerId:1});
    expect(onRegion).toHaveBeenCalledWith([20,30,100,130]);
  });
});
