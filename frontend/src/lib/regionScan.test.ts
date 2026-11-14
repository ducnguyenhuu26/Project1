import { describe, expect, it } from 'vitest';
import type { Detection, Scan } from '../types';
import { mergeRegionScan } from './regionScan';

const detection=(id:string):Detection=>({id,class_id:0,category_id:'plastic',label:'Nhựa',material_id:'plastic',confidence:.8,bbox_xyxy:[10,10,30,30],origin:'ai',status:'supported',model_version:'test'});
const scan=(detections:Detection[]):Scan=>({mode:'real',model_version:'test',taxonomy_version:'1',supported_category_ids:['plastic'],image_width:200,image_height:100,detections,summary:[{category_id:'plastic',material_id:'plastic',name:'Nhựa',estimated_count:detections.length}],advice:[],warnings:[]});

describe('merging a second detection pass',()=>{
  it('appends a fresh identity without changing the first scan',()=>{
    const original=scan([detection('det-1')]);
    const region=scan([detection('det-1')]);
    const merged=mergeRegionScan(original,region,[20,20,80,80],()=>'new-id');
    expect(merged.added[0].id).toBe('region-new-id');
    expect(merged.scan.detections.map(d=>d.id)).toEqual(['det-1','region-new-id']);
    expect(merged.scan.summary[0].estimated_count).toBe(2);
    expect(original.summary[0].estimated_count).toBe(1);
  });
  it('keeps an unmatched drawn region for manual KB confirmation',()=>{
    const merged=mergeRegionScan(scan([]),scan([]),[20,20,80,80],()=>'missing');
    expect(merged.added[0]).toMatchObject({id:'manual-region-missing',category_id:null,origin:'manual',confidence:null,bbox_xyxy:[20,20,80,80]});
  });
});
