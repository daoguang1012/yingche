#version 330 core
in vec2 uv;
out vec4 frag;
uniform sampler2D frameTex;
uniform sampler2D originalTex;
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
uniform float smoothValue, detailValue, whiteValue, warmValue, pinkValue;
uniform float slimValue, eyesValue, chinValue, noseValue, lipValue, blushValue, sharpValue;
float distancePx(vec2 a, vec2 b) { return length((a-b)*imageSize); }
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
        vec2 left=points[k+2], right=points[k+3], center=(left+right)*.5;
        float width=distancePx(left,right);
        t=eyeWarp(t,points[k],width*.21,eyesValue*.0028*trackingWeight);
        t=eyeWarp(t,points[k+1],width*.21,eyesValue*.0028*trackingWeight);
        t=moveWarp(t,left,(left-center)*slimValue*.0015*trackingWeight,width*.55);
        t=moveWarp(t,right,(right-center)*slimValue*.0015*trackingWeight,width*.55);
        vec2 chin=points[k+4], nose=points[k+5];
        t=moveWarp(t,chin,(nose-chin)*chinValue*.0015*trackingWeight,width*.5);
        t=moveWarp(t,points[k+6],(points[k+6]-nose)*noseValue*.003*trackingWeight,width*.19);
        t=moveWarp(t,points[k+7],(points[k+7]-nose)*noseValue*.003*trackingWeight,width*.19);
    }
    p=vec2(t.x,1.0-t.y);
    vec3 src=sourceAt(p);
    if(enabled==0) {frag=vec4(src,1.);return;}
    vec2 maskUV=t;
    for(int i=0;i<faceCount;i++) {
        vec2 center=(points[i*8+2]+points[i*8+3])*.5;
        if(distancePx(t,center)<distancePx(points[i*8+2],points[i*8+3])*.8)maskUV=t-faceMotion[i];
    }
    vec3 masks=texture(regionTex,maskUV).rgb*trackingWeight;
    vec3 skin=src;
    float bright=whiteValue/200.;
    if(gpupixelEnabled==1 && bright>=0.) bright=0.;
    if(bright>=0.) skin=mix(skin,sqrt(max(skin,vec3(0.))),bright*.9);
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
