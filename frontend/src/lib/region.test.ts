import { describe, expect, it } from 'vitest';
import { imagePoint, regionFromPoints } from './region';

describe('region drawing coordinates', () => {
  it('maps pointer positions through contain letterboxing', () => {
    const rect = {left:100,top:50,width:400,height:400};
    expect(imagePoint(200,150,rect,200,100)).toEqual({x:50,y:0});
    expect(imagePoint(400,350,rect,200,100)).toEqual({x:150,y:100});
    expect(imagePoint(200,100,rect,200,100)).toBeNull();
    expect(imagePoint(600,400,rect,200,100,true)).toEqual({x:200,y:100});
  });
  it('normalizes a drag in either direction', () => {
    expect(regionFromPoints({x:90,y:80},{x:20,y:10})).toEqual([20,10,90,80]);
  });
});
