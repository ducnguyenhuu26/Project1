// @vitest-environment jsdom
import { useState } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ItemSession } from '../types';
vi.mock('../lib/language', () => { const t = (viText: string) => viText; return { useLanguage: () => ({ t }) }; });
import { RecommendationWizard } from './RecommendationWizard';

const empty = (): ItemSession => ({confirmedObjectId:'',answers:{},recommendation:null});
const objects = [
  {id:'plastic_bottle',name_vi:'Chai nhựa',category_id:'plastic',aliases_vi:[]},
  {id:'release_liner',name_vi:'Lớp lót băng dán',category_id:'paper',aliases_vi:['urgo']},
];
const json = (body: unknown) => Promise.resolve({ok:true,json:async()=>body} as Response);
afterEach(() => {cleanup();vi.unstubAllGlobals();});

function Harness() {
  const [focus,setFocus] = useState('a');
  const [sessions,setSessions] = useState<Record<string,ItemSession>>({a:empty(),b:empty()});
  return <><button onClick={()=>setFocus(focus==='a'?'b':'a')}>Switch item</button>
    <RecommendationWizard key={focus} categoryId={focus==='a'?'textile':'plastic'} detectedCategoryId={focus==='a'?'textile':'plastic'} source={focus==='a'?'corrected':'detected'} session={sessions[focus]} onSessionChange={next=>setSessions(previous=>({...previous,[focus]:next}))}/>
    <output data-testid="saved-a">{sessions.a.recommendation?.headline}</output>
    <output data-testid="saved-b">{sessions.b.recommendation?.headline}</output></>;
}
describe('KB confirmation and request lifetime', () => {
  it('keeps unrestricted accent-insensitive search, category toggle and no-match state', async () => {
    vi.stubGlobal('fetch', vi.fn((input: string) => {
      const url = new URL(input,'http://localhost');
      const q = url.searchParams.get('q') || '';
      const category = url.searchParams.get('category_id');
      const items = objects.filter(o => (!category||o.category_id===category) && (!q||o.aliases_vi.includes(q)||o.name_vi.toLowerCase().includes(q)));
      return json({items,count:items.length,total_count:166});
    }));
    render(<Harness/>);
    await screen.findByRole('option',{name:'Lớp lót băng dán'});
    fireEvent.change(screen.getByPlaceholderText('Ví dụ: vỏ chuối, áo cũ, pin…'),{target:{value:'urgo'}});
    await screen.findByRole('option',{name:'Lớp lót băng dán'});
    fireEvent.click(screen.getByRole('checkbox'));
    await screen.findByText('Không tìm thấy đồ vật phù hợp. Thử từ khóa khác.');
    fireEvent.click(screen.getByText('Không tìm thấy / tra cứu toàn bộ'));
    await screen.findByRole('option',{name:'Lớp lót băng dán'});
  });
  it('ignores a late evaluation from a different detection', async () => {
    let release!: (value: Response) => void;
    vi.stubGlobal('fetch', vi.fn((input: string, init?: RequestInit) => {
      if (input.includes('/catalog')) return json({items:objects,count:2,total_count:166});
      if (input.includes('/objects/')) return json({id:'release_liner',name_vi:'Lớp lót băng dán',category_id:'paper',questions:[{id:'material',label:'Chất liệu',options:[{id:'unknown',label:'Chưa rõ'}]}],notice:''});
      if (input.includes('/evaluate')) {
        expect(JSON.parse(init!.body as string)).toMatchObject({object_id:'release_liner',source:'corrected',detected_category_id:'textile'});
        return new Promise<Response>(resolve=>{release=resolve;});
      }
      throw new Error(input);
    }));
    render(<Harness/>);
    await screen.findByRole('option',{name:'Lớp lót băng dán'});
    fireEvent.change(screen.getByLabelText('Đồ vật cần hướng dẫn'),{target:{value:'release_liner'}});
    await screen.findByText('Chất liệu');
    fireEvent.click(screen.getByLabelText('Chưa rõ'));
    fireEvent.click(screen.getByText('Xem hướng xử lý'));
    fireEvent.click(screen.getByText('Switch item'));
    release({ok:true,json:async()=>({status:'complete',headline:'Stale result'})} as Response);
    await waitFor(()=>expect(screen.getByTestId('saved-a').textContent).toBe(''));
    fireEvent.click(screen.getByText('Switch item'));
    expect(screen.queryByText('Stale result')).toBeNull();
  });
  it('uses the confirmed object and renders authored safety detail', async () => {
    const requests: unknown[] = [];
    vi.stubGlobal('fetch', vi.fn((input: string, init?: RequestInit) => {
      if (input.includes('/catalog')) return json({items:objects,count:2,total_count:166});
      if (input.includes('/objects/')) return json({id:'release_liner',name_vi:'Lớp lót băng dán',category_id:'paper',questions:[{id:'material',label:'Chất liệu',options:[{id:'unknown',label:'Chưa rõ'}]}],notice:''});
      if (input.includes('/evaluate')) {
        requests.push(JSON.parse(init!.body as string));
        return json({status:'complete',headline:'Giữ riêng lớp lót',assessment:'Chất liệu chưa rõ',stream_label:'Cần xác minh',recommendation:'Không mặc định tái chế giấy.',context_response:'Xác minh thành phần trước khi xử lý.',practical_steps:['Giữ riêng'],why:'Vật liệu pha trộn',avoid:['Không trộn với giấy'],cautions:['Không rõ lớp phủ'],next_step:'Hỏi nơi tiếp nhận',sources:[{id:'R1',title:'Nguồn KB',scope:'Nguyên tắc',url:'https://example.org'}],notice:'Chưa xác minh tuyến địa phương',local_collection_verified:false});
      }
      throw new Error(input);
    }));
    render(<Harness/>);
    await screen.findByRole('option',{name:'Lớp lót băng dán'});
    fireEvent.change(screen.getByLabelText('Đồ vật cần hướng dẫn'),{target:{value:'release_liner'}});
    await screen.findByLabelText('Chưa rõ');
    expect(screen.getByText(/khác nhóm gợi ý textile/)).toBeTruthy();
    fireEvent.click(screen.getByLabelText('Chưa rõ'));
    fireEvent.click(screen.getByText('Xem hướng xử lý'));
    await screen.findByRole('heading',{name:'Giữ riêng lớp lót'});
    expect(requests).toEqual([{object_id:'release_liner',answers:{material:'unknown'},source:'corrected',detected_category_id:'textile'}]);
    expect(screen.getByText('Không mặc định tái chế giấy.')).toBeTruthy();
    expect(screen.getByText('Xác minh thành phần trước khi xử lý.')).toBeTruthy();
    expect(screen.getByText('Giữ riêng')).toBeTruthy();
    expect(screen.getByText('Hỏi nơi tiếp nhận')).toBeTruthy();
    expect(screen.getByRole('link',{name:/R1 · Nguồn KB/})).toBeTruthy();
  });
});
