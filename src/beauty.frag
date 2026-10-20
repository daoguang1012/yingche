#version 330 core
in vec2 uv;
out vec4 frag;
uniform sampler2D frameTex;
uniform sampler2D originalTex;
uniform sampler2D baseTex;
uniform int gpupixelEnabled;
uniform float trackingWeight;
uniform vec2 faceMotion[4];
uniform sampler2D regionTex;
uniform sampler2D swapTex;
uniform int swapEnabled;
uniform int swapPrecomposed;
uniform float swapStrength;
uniform vec2 texel;
uniform vec2 imageSize;
uniform int enabled;
uniform int compareMode;
uniform int faceCount;
uniform int trackedFaceCount;
uniform vec2 points[32];
uniform float effectWeights[4];
uniform float smoothValue, detailValue, whiteValue, warmValue, pinkValue;
uniform float slimValue, eyesValue, chinValue, noseValue, lipValue, blushValue, sharpValue;
float distancePx(vec2 a, vec2 b) { return length((a-b)*imageSize); }
float luma(vec3 c){return dot(c,vec3(.299,.587,.114));}
// Frequency-separated skin: GPUPixel supplies only the smoothed fine texture. Large-scale shading
// and skin hue come from the unfiltered frame, so the face keeps its form and colour and matches
// the neck; chroma is only partly evened out to soften blotches and redness.
vec3 skinTone(vec2 p,float radius){
    vec3 b=texture(baseTex,p).rgb,g=texture(frameTex,p).rgb,lowB=vec3(0.),lowG=vec3(0.);
    for(int i=0;i<12;i++){
        float a=float(i)*.5235988;vec2 o=floor(vec2(cos(a),sin(a))*radius*((i&1)==0?1.:.55)+.5)*texel;
        lowB+=texture(baseTex,p+o).rgb;lowG+=texture(frameTex,p+o).rgb;
    }
    lowB/=12.;lowG/=12.;
    // Smoothing attenuates mid-scale texture (spots, fine lines); texture retention spares part of it.
    // Colour is kept as colour-minus-luma, so zero settings reproduce the frame exactly.
    float s=clamp(smoothValue/100.,0.,1.),keep=clamp(detailValue/150.,0.,1.);
    float yb=luma(b),yl=luma(lowB);
    float y=yl+(luma(g)-luma(lowG))*(1.-.75*s*(1.-.5*keep));
    return clamp(vec3(y)+mix(b-yb,lowB-yl,s*.5),0.,1.);
}
vec2 eyeWarp(vec2 p,vec2 c,float radius,float amount) {
    float t=clamp(1.0-distancePx(p,c)/max(radius,1.0),0.0,1.0);
    return c+(p-c)*(1.0-amount*t*t);
}
vec2 moveWarp(vec2 p,vec2 c,vec2 delta,float radius) {
    float t=clamp(1.0-distancePx(p,c)/max(radius,1.0),0.0,1.0);
    return p+delta*t*t*(3.0-2.0*t);
}
vec3 sourceAt(vec2 position) {
    vec3 base=texture(frameTex,position).rgb;
    if(swapEnabled==1 && swapPrecomposed==0) {
        vec2 sampleUV=vec2(position.x,1.-position.y);
        float nearest=1.;vec2 offset=vec2(0.);
        for(int i=0;i<trackedFaceCount;i++) {
            vec2 center=(points[i*8+2]+points[i*8+3])*.5;
            float d=distancePx(sampleUV,center)/max(1.,distancePx(points[i*8+2],points[i*8+3])*.9);
            if(d<nearest){nearest=d;offset=faceMotion[i];}
        }
        sampleUV-=offset;
        vec4 face=texture(swapTex,sampleUV);
        return mix(base,face.rgb,face.a*swapStrength);
    }
    return base;
}
void main() {
    // mpv's FBO is rendered with FLIP_Y=1. Region maps use top-down image coords.
    vec2 p=uv;
    if((enabled==0 && swapEnabled==0) || (compareMode==1 && uv.x<.5)) {
        frag=texture(originalTex,p); return;
    }
    vec2 t=vec2(p.x,1.0-p.y);
    for(int i=0;i<faceCount;i++) {
        int k=i*8;
        float weight=trackingWeight*effectWeights[i];
        vec2 left=points[k+2], right=points[k+3], center=(left+right)*.5;
        float width=distancePx(left,right);
        t=eyeWarp(t,points[k],width*.21,eyesValue*.0028*weight);
        t=eyeWarp(t,points[k+1],width*.21,eyesValue*.0028*weight);
        t=moveWarp(t,left,(left-center)*slimValue*.0015*weight,width*.55);
        t=moveWarp(t,right,(right-center)*slimValue*.0015*weight,width*.55);
        vec2 chin=points[k+4], nose=points[k+5];
        t=moveWarp(t,chin,(nose-chin)*chinValue*.0015*weight,width*.5);
        t=moveWarp(t,points[k+6],(points[k+6]-nose)*noseValue*.003*weight,width*.19);
        t=moveWarp(t,points[k+7],(points[k+7]-nose)*noseValue*.003*weight,width*.19);
    }
    p=vec2(t.x,1.0-t.y);
    vec3 src=sourceAt(p);
    if(enabled==0) {frag=vec4(src,1.);return;}
    vec2 maskUV=t;float radius=6.;
    for(int i=0;i<faceCount;i++) {
        vec2 center=(points[i*8+2]+points[i*8+3])*.5;float width=distancePx(points[i*8+2],points[i*8+3]);
        if(distancePx(t,center)<width*.8){maskUV=t-faceMotion[i];radius=max(3.,width*.07);}
    }
    vec3 masks=texture(regionTex,maskUV).rgb*trackingWeight;
    // GPUPixel remains the texture filter, but only current supported skin is blended.
    if(gpupixelEnabled==1)src=mix(texture(baseTex,p).rgb,skinTone(p,radius),masks.r);
    vec3 skin=src;
    float bright=whiteValue/200.;
    // Luminance-only lift: brightens without washing the skin towards grey.
    float yy=luma(skin);
    if(bright>=0.) skin+=vec3(bright*1.2*yy*(1.-yy));
    else skin*=1.0+bright*.65;
    skin+=vec3(.055,-.012,-.055)*(warmValue/100.);
    skin+=vec3(.035,-.015,.005)*(pinkValue/150.);
    vec3 color=mix(src,clamp(skin,0.,1.),masks.r);
    float lum=dot(color,vec3(.2126,.7152,.0722));
    vec3 lipColor=vec3(.70,.13,.24)*(.5+lum*.8);
    color=mix(color,lipColor,masks.g*clamp(lipValue/150.,0.,1.)*.75);
    color=mix(color,vec3(.88,.30,.38)*(.6+lum*.5),
              masks.b*clamp(blushValue/150.,0.,1.)*.28);
    if(compareMode==1 && abs(uv.x-.5)<texel.x) color=vec3(.55,.85,.77);
    frag=vec4(clamp(color,0.,1.),1.);
}
