"""Offline display-buffer decoding and crease-aware lighting; never edits a mesh."""

SCRIPT = r'''
const displayMeshCache=new WeakMap();
function displayBuffer(encoded,Type,count){
  const text=atob(encoded);
  if(text.length!==count*4)throw Error('Tamanho inválido da malha de visualização.');
  const bytes=new Uint8Array(text.length);
  for(let i=0;i<text.length;i++)bytes[i]=text.charCodeAt(i);
  if(new Uint8Array(new Uint32Array([1]).buffer)[0]===1)return new Type(bytes.buffer);
  const view=new DataView(bytes.buffer),values=new Type(count);
  for(let i=0;i<count;i++)values[i]=Type===Float32Array?view.getFloat32(i*4,true):view.getUint32(i*4,true);
  return values;
}
function displayMesh(object){
  const key=object.mesh||object.triangles||object;
  if(displayMeshCache.has(key))return displayMeshCache.get(key);
  let positions,indices;
  if(object.mesh){
    const mesh=object.mesh;
    if(mesh.encoding!=='indexed-f32-u32-le-v1')throw Error('Formato de visualização desconhecido.');
    positions=displayBuffer(mesh.positions,Float32Array,mesh.vertex_count*3);
    indices=displayBuffer(mesh.indices,Uint32Array,mesh.triangle_count*3);
  }else{
    const points=[],faces=[],welded=new Map();
    for(const triangle of object.triangles||[])for(const point of triangle){
      const key=point.join(',');
      if(!welded.has(key)){welded.set(key,points.length/3);points.push(...point)}
      faces.push(welded.get(key));
    }
    positions=new Float32Array(points);indices=new Uint32Array(faces);
  }
  for(const index of indices)if(index*3>=positions.length)throw Error('Índice inválido na visualização.');
  for(const value of positions)if(!Number.isFinite(value))throw Error('Coordenada inválida na visualização.');
  const result={positions,indices};displayMeshCache.set(key,result);return result;
}
function displayShades(positions,indices){
  const count=positions.length/3,normals=new Float32Array(indices.length),
    counts=new Uint32Array(count),offsets=new Uint32Array(count+1),
    lengths=new Float32Array(indices.length/3),weights=new Float32Array(indices.length);
  for(let i=0;i<indices.length;i+=3){
    const a=indices[i]*3,b=indices[i+1]*3,c=indices[i+2]*3,
      ux=positions[b]-positions[a],uy=positions[b+1]-positions[a+1],uz=positions[b+2]-positions[a+2],
      vx=positions[c]-positions[a],vy=positions[c+1]-positions[a+1],vz=positions[c+2]-positions[a+2];
    normals[i]=uy*vz-uz*vy;normals[i+1]=uz*vx-ux*vz;normals[i+2]=ux*vy-uy*vx;
    const area=Math.hypot(normals[i],normals[i+1],normals[i+2]),dot=ux*vx+uy*vy+uz*vz;
    lengths[i/3]=area;
    weights[i]=Math.atan2(area,dot);
    weights[i+1]=Math.atan2(area,ux*ux+uy*uy+uz*uz-dot);
    weights[i+2]=Math.atan2(area,vx*vx+vy*vy+vz*vz-dot);
    counts[indices[i]]++;counts[indices[i+1]]++;counts[indices[i+2]]++;
  }
  for(let i=0;i<count;i++)offsets[i+1]=offsets[i]+counts[i];
  const cursor=offsets.slice(),adjacent=new Uint32Array(indices.length);
  for(let i=0;i<indices.length;i++)adjacent[cursor[indices[i]]++]=i;
  const shades=new Float32Array(indices.length),crease=Math.cos(Math.PI/4),lightLength=Math.hypot(.3,-.4,.86);
  for(let corner=0;corner<indices.length;corner++){
    const face=corner-corner%3,vertex=indices[corner],length=lengths[face/3];
    let x=0,y=0,z=0;
    // Very large triangle fans must not create quadratic work. Their singular
    // corner retains the face normal; every source triangle is still rendered.
    if(counts[vertex]>64){x=normals[face];y=normals[face+1];z=normals[face+2]}
    else for(let j=offsets[vertex];j<offsets[vertex+1];j++){
      const adjacentCorner=adjacent[j],neighbor=adjacentCorner-adjacentCorner%3,other=lengths[neighbor/3];
      if(!length||!other)continue;
      const dot=(normals[face]*normals[neighbor]+normals[face+1]*normals[neighbor+1]+normals[face+2]*normals[neighbor+2])/(length*other);
      if(dot>crease+1e-6){const weight=weights[adjacentCorner]/other;x+=normals[neighbor]*weight;y+=normals[neighbor+1]*weight;z+=normals[neighbor+2]*weight}
    }
    shades[corner]=.42+.58*Math.min(1,Math.abs((.3*x-.4*y+.86*z)/(lightLength*Math.max(1e-12,Math.hypot(x,y,z)))));
  }
  return shades;
}
function displaySurface(objects){
  const meshes=objects.map(object=>({object,...displayMesh(object)}));
  const total=meshes.reduce((sum,mesh)=>sum+mesh.indices.length,0),flat=new Float32Array(total*3),shades=new Float32Array(total);
  let offset=0;
  for(const {object,indices,positions:source} of meshes){
    let positions=source;
    if(object.display_rotation){
      positions=source.slice();const {radians:a,center:[x,y]}=object.display_rotation,c=Math.cos(a),s=Math.sin(a);
      for(let i=0;i<positions.length;i+=3){const dx=source[i]-x,dy=source[i+1]-y;positions[i]=x+c*dx-s*dy;positions[i+1]=y+s*dx+c*dy}
    }
    const lighting=displayShades(positions,indices);
    for(let i=0;i<indices.length;i++){
      const vertex=indices[i]*3,target=(offset+i)*3;
      flat[target]=positions[vertex];flat[target+1]=positions[vertex+1];flat[target+2]=positions[vertex+2];
    }
    shades.set(lighting,offset);offset+=indices.length;
  }
  return {flat,shades,triangleCount:total/3};
}
function displayRayDistance(flat,origin,direction){
  let nearest=Infinity;
  const [ox,oy,oz]=origin,[dx,dy,dz]=direction;
  for(let i=0;i<flat.length;i+=9){
    const ax=flat[i],ay=flat[i+1],az=flat[i+2],
      ux=flat[i+3]-ax,uy=flat[i+4]-ay,uz=flat[i+5]-az,
      vx=flat[i+6]-ax,vy=flat[i+7]-ay,vz=flat[i+8]-az,
      px=dy*vz-dz*vy,py=dz*vx-dx*vz,pz=dx*vy-dy*vx,
      det=ux*px+uy*py+uz*pz;
    if(Math.abs(det)<1e-12)continue;
    const tx=ox-ax,ty=oy-ay,tz=oz-az,u=(tx*px+ty*py+tz*pz)/det;
    if(u<0||u>1)continue;
    const qx=ty*uz-tz*uy,qy=tz*ux-tx*uz,qz=tx*uy-ty*ux,v=(dx*qx+dy*qy+dz*qz)/det;
    if(v<0||u+v>1)continue;
    const distance=(vx*qx+vy*qy+vz*qz)/det;
    if(distance>=0&&distance<nearest)nearest=distance;
  }
  return Number.isFinite(nearest)?nearest:null;
}
'''
