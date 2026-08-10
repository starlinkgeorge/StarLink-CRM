"""Import the 2025 StarLink Montessori Materials catalogue into the CRM.

The source catalogue contains 494 products. This import is idempotent: it
creates only missing SKUs and attaches an image only where a product has none.
Existing product data remains untouched.

Run inside the rebuilt backend container:
    python scripts/import_montessori_materials_catalog.py
"""

from base64 import b85decode
from decimal import Decimal, InvalidOperation
from gzip import decompress
import json
from os import getenv
from pathlib import Path
import sys

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import get_session_factory
from app.models.product import Product, ProductCategory, ProductImage


ROOT_CATEGORY_NAME = "2025 Montessori Materials"
CATEGORY_ORDER = (
    "Practical Life",
    "Sensorial",
    "Language",
    "Mathematics",
    "Biology",
    "Geography",
    "Infant & Toddler",
    "Educational Toys",
    "Role Play",
)
IMAGE_BASE_URL = getenv(
    "PRODUCT_IMAGE_BASE_URL", "http://localhost:5173/product-images"
).rstrip("/")
SOURCE_NOTE = "Imported from the 2025 StarLink Montessori Materials catalogue."

# Compact, lossless catalogue data extracted from the customer-supplied PDF.
# It is decoded locally; no network access is used during import.
_COMPRESSED_PRODUCTS = "ABzY8tSWhG0{_jOTXWpDl7RmT%MWLhs`V5B-u))Yw`{CfYbj3c?SY!1Bp!3fIV2~J&es0-1xU`QyFp+GStIHt_DELzxdAl#hVK9R-&f7I?W;GhE<e4#c<s9E)xW+f({(1k@<&yzveLP#(|hM~ofd`o)~3#v@_W&Ox#DAymACDk_{@_<B0hi5SKUXJEMoETF3WH4TJbqp1oFGPkM4rY&&#yUZmarUeC47}mu<dG3+GdQlfC-Ce<fIa9P2z^t%?kA#fyMLF3;~kc3j-2Tnux0c39px)~B?-g;YW~0ip^P5u^$hA*6~hlWz&-KR}&s+qNq6^457@i?29;<n3Kg=k(udOtN#4>^v7TvPJY`D;gZ2>~`Gjl;H#Ar*yeT#614<@kBss)pzIWetx9*0qJ8^eREFAmGkaCo0%$kpt?+Nvi9D&$jfG4s7__>pvrW!nSJpXQ1}0tzXTwl=+BC(y~`Tsm$J#~c2EVgfq770Ex#3GqGIBI`;16H(SOZ~WnIk;1a$i4U6nb5%6waAP4fce1(Z2PaxU9cXs!2E?J(Yd30^rtvWNm=Rlxgu__zm6V#wLsJ{Fij$A7Ap-<;FxF972S)5=3Itg~A7rWZ#t^C61(la?$%x&M}ZcSd*uw&2JV^y1E%*&8<@Uc(pzC6+*mBAm2d0UR#=jc7~xc&+3|WCAkG<6GfypwX|si}NS8R8}|6hdOOGfGX_w>K=+kNJhiQJ(ExNd1MC#l)Ai#|K@y@yZdDI_ifXr*G1-B-POW)_#$8pMk<SmNpCPwgT#)IPdJI8dJs8ZL?J$i@EC^ON!v5VKeVzQx`@P1>#WlA>d#JsQlgFVR3b7@%f%PWQg%S=U*_wLfa&-QE6HQ*1jX11@~9IO#CAkL?Y}Q7v2^EY>wK(=RaQISrPRLPWmy5m6$T3*TJhz!DE5H;haKMVE%eEP4e0#dqc}_JP1XVyzdv7lX@xFS7w`u9K@_0Zd%sm>5q=@kr7>g)pO7VnevNbo6%^s&BR`8V$Pzsv3pCX?Ro!;VK<uK^v`EWk_R~cnT<X(%=Y5v7KSS%mTXbgr!<mEn%0v2!V_gt2s~zsS6A`6aFe756I(&S<Tu@Lu-`@kOzZp1N8IkCY;j-G6t+<|k^4*Iw=kjO6YV$~Yg?qiZ0pb&OSGYG~;(tkz0^`xbMcOnR0!X{N$VcWD)~DQZZ9Ns|V^ufMPUS+oqkAU~kUlkpx>$c>S@8H!O_aF<0!v6!kOgy*4Tx{T5HFbJjpG6R?m1`GdXv`eIxAb}a@b-DTZlHju*vZ1Ej$Aqx0Dyq@ctA!vDKM&s|z-h<Sb6(B@U)u<mET#s`{SQ&}#4(%*T>~`wDqK+{YVBEHOEEmsu&!e4Z962t0CC+18b~2k(TOIwdxW#>h=11jDhMke}gFrQn8>;lKfWpRV)b-nq<L4HaL+7%S1bJ`s&M$I)aY7(%W7>P^41?R935SG@3(C$VS@SkS-T+sUIi(Za`a3b2zH;3LS01;~@hq5{Y7RCpDowBU1y60(JhRTbJu$a5BoHo(4f$S0FTrcFN1Mt3=PvCrdorm=pPv&nGr=qA@tCD?~O%3exF*X>RJ`%mfeA6vY?8L?zIQt7TS+d~}+Jr)d+{#sVo*V)QByD#!`CEe;%>F7W|BH_J-^x*ABNKJW2Bg8m>6!gKTX<Te{{S-u_t_tzy3TQ5hY_4eX)`wA3iS_xWBP)bwJ&GpGP9NWa9=@T`p=1HQdH7^a3d5$t#aK1nVVuIqu?9QF8Gr%QFJcwHRLG}StUl&)q(x(V2ZlsQlVt?d`uTk$EOg;Zq_=NAWYs!r1&nifmu^rXB&5z+fa6Kr6iu4U1yuX{ylz?<`IGB*Ruy6quVf&kZ4BNk@)!@O2!FbYh~Q>lR^l2wz@?l-9-x58A++gQ0%-ZGySzR~rfe}D;><7!X${N#;9R(qFKQS$eV<;-Z6)Ct@8PU8SA?%cZ;=o)d9uV{0QEGLP$SDH{?*t@ju!gMCsfS7$t*y}f2p>&cU>y;a$O0hu#Yo0y(NeP;KIibakvc~MI6|rDU4*Y4G&|c7cyqLt+VlaM>x+BP7pvIhSx4$5cM$GZif-ltGldTPg^{(mpFD+u@c1z0=LicO#=ez{3=^-vN~<0kWQ<%EsXB`5t)E)ze=0VAAR>%RxfiDU{KbKd-%kWRb%escR7rRR@+{C;wZb{M+h`d7LL6rM$7d5gYEUEt+&FN{xcK)dY+cI1!9VYyUU28^ig3C5>L1wmvJ=xoW&Zf(_%Z$ri9x=VoYHj?%^1pYvISEQ0Y1=x+HYJy&HosD&-Lv!b9qA3MLx~Ff{sLu)NLIo#@gwuawZ0z~g8wgG3i`r@0Bfa3>23#zG&+&eH3=M1k&vkziv0^`(a-#nHA(7XIYj4x^qAG{P8OJDpt&<>N0nw(flG`STy^GQhAW;1R~NbMf^|Wm<&ck*#qU_#BbY$jYg99WpqH?Zn6)r=fKN8BpS9dA-~gsqkU`u}#J0B29#yQh+)%Uc@mj`NOWCk9Rp?^QQ0ea7=2KRgsTdD~jtUzJSnha-7p>b~1g3MPp<aMOtRg`}|hi%#A)^b(9Sj!>C@-HqPIi-?rix>5jg3POweqVH*nWtk{$ZpT2U55$6<}2Uwx|9&!_yDP}#{L-1W_|E|;0IjNU-FjLAGA>P!e(8D9=jbqI{-6`-#HTQ+^f$Lrs5Cfc=m;v^Ny$GA&!6OY`A4XZ0GQ)s56uXHtWL9#9PrZ8WCX?eTz6V)Sq<fU>-}el<hwPSUa!AwnM;*#g^(U3elB2nkJ~X$h?eb2-Y}chxIxaT;UFvdEOMCLY;fK(alo5b0S(B}=yPWYudMa&T?$Z~-@kmWvfNJ6}UqrHvll6}e^z&z-lRxx%MwxDO&bAvAiVK1x>t-KCPU<WhLMCtX=9}}OuC~|uWc8Ete8Q=_^Q=vat_rmsu2f>s`bl3?wqLTy(-uzkF)?uQll%0Ouq3wWZKe`&O7yubAcb%{V)i6r(KA4oUzQcfU@jETGvfda#Mq#BdJ^X%E0=jOR3Vw_13h|`E=U%UIJn{D1q)zdd{+!5#pMlX*t(7bZQv9;AXFQ<@l+h>_b=<TtM$IR6M85uSJ(JL^%oIVkqlS628NgxTd-g%5{%>uicNRJf0C(8anCoI^C@d(y~>-jZQTeL+<4cbiVW)DlH7_gM!czv@ifL+*pe}}-!~f@HXq-`A-;<_$Lh+Thz9d`Z-w?Q`h7M?PsO4IKe+yg>2uX=F?F}W6rK)gY^M>lBj_=hzU!;;c4ej~#pW)(&e}KPR(4ik*Nu2~is2B%IFk?>;=Wv|;?mQ4(`eyFoD<il6`&NiH+js$^@JISD~}VD3KU8)G<X?INj2+vgK4~G={_TGh?A%?Aku|O<>7KJ?=lp!;at%_+Pr1_SR!z({I*?R3o-p|IN;7zjzgtt0?xxen~Rh5q}DK=di%o6;Az?jUuh`o`%tIrwG1cSudl0OG-RXdY|j{84$Kh=JtMqMWB_R#jz)7Mnw|5t;UvZPrtb!{Y%ovwB}-S*csVK4;=ak7H%_0O?u&g+N+mu(!-Rf-R~Y+y=F$~CAu|yUiE169vcx_NVECl|mL3c?6%mz*lx-&6&>f@0nx2fyV~Y;07xv|RN4x@IGI7F@P##p{XWpc$TFJV4Q*C&dQruy^&v$tjoHk?f{Yj{e`EnG6@(@v^)F$eQ0+r~j62FWj@`7ODM@L>a<$c9;y{5$N$SUHfCdqX8lLZEEgKArfyWne9Ukf*}t*e#H?Nud;mn-GMNrazn0mOt<3oC67CU3M@T~=CV;Nq+57^|6}7{lO73xO<0>ZoOYC3vbdo)!t_7p1rQKCRd21!>a%zm6ysm`Hq^wOOAIK3V;J_}y4O-|J8GF{ywu-&=-n#b4jQ^*C_Uc7?Y4`T`vDAcrlPWO|+Bu$f$~!TchHbsnS7AzfyuKlHE*N{-Zd+TLaBw9S`|io-{%Hpi*NnkBwA4;<nsOkx(05y~5@;s#7YLyc7<Di2#pc7f<3>Lz=k1)}0JLA)_l9xtNE@IspTG~r1E7+Jstun;O2X3R?BWp!HY(Wpp|5j-|B!fSDpm-4Y6vG}Ot5%eWK4~FxCoJq2t^zpk92i$>v;0#3LD;d(-k!V5O4G-H^@#9xA#u<o#3(&YY4SS@;8V#fMyJuWRoU|=q`r=#V$$-T%gh8~kZR>pAw!57!mBiWboX=Rf8K5#L#;C#KnF|k$c#IsxF*soeW?5-KJkFXjK7~!F+2<z%>L1ylSC#WNTjoODI{&^+%QkQCM-5UQ^lmdu5OTc6By<)$`h>#ZnGSYm;mezKj90it*je*k!(+~v2BK`v3%D7W>wJ(&m(n>E&bae&TdrzxQS?<i#%ilrSLxxI3oDFduu2DDUENjNMw$TfaT&JPaJi!vifCU8JA~m&Ves1wf}%IWL_rP7t*KP;NQ!X^9(~5|`&w7hGe0;r;(@y&*+0#Nt7sG%d1o^O8^I+Xnalf4Xs8#-PI8ACm50Q*xSrGS;^XfNuJ#rjOtk)G(3?J+@DqFOB(CfJY%1CyHSLCsEu)Y0jEL~s_<E+}Q}C200Hmmn8%?IbW|h4ILhSAJQ6VZt=Dt>l=mc9_7%*U_3UJS+pt*|}m%Kvd5*Z`3+`=K`_yz5H<9r|;sg#%$!xdZ}t_{NH)dB?eqS{@gqd>`1bxJYfMDXcECWB;G@{Z~sz2IoDxW1E^6eAj|%Spc*8($fQ#X2r|YYsL!u31nzERnJf5Bu*VAk1vkSTe#SJAd5b2eWi1`M9?ki;OxUwm5VsMuvri9T%mii=B{ckbti5MdRF5^-$E+39Nf=OkN6^-YrE26%bl%DHu1~SrfF0n7D38tmSxH9Q7Yjo~>&M`z`w%D+x9FeS4RRpGlj;BJ+HjaQ2L$^2Fi@qJn%RGr7r3ltgT}GAA&<^|x8n5OqS7-7Dpu7mRs1S_~ofOlU}=(uym(|1As%Se8%Gpx4Ixh~aVX9axgTi{+ivb@jb@V_=gh@8gGsV0}J?Q5(qyBpHI=d$`!ne|+#0*67P#H$~QFJ(u{YOqR0ZYA^OwMVLk?1|Ru%uXH-)br_HZAx=>WGZbol-|&KmsaYf=B+Qq{EtWPDA!Ps~KE4paJ#eyG<$YeVOuuE+Bor=L;%dt?4|FiHu`6JO{{vE6=NnbADm4}^&P_0^z<l#tEF)DgLiO$++wQGl<8)O=+jY~W0e%`>B<X+rZ0NAkRV!m5Ciu2Wh)-$Zbiii-BfuvQz*wf#Ge<Qcj5MEM^iE(FcLID0&=dZdbyfG9{<5OV&i6_C|IjmJqDakDVgnZIz)Z!XK}_1~YfVSKu+bp!LfBr*=dDZqDOGxV(Nh{?PcnXV&>{eL!n-1qz0cD6-uW%NO*?sw;)TL$i1fuOB*#N`zh|+80Yg%I5ZbsNp-zB}9uZQr&?5oYEa$_~+*xWmHKJDLS*j7wW|_TlK|bIfQXogA^T+8-T7;GX*k}=MagPOofz8-<l4G|oF=Q%uAE%j$1nz|MZPDhNB475e<vTm%G_9Ra>3y~B9vS`=1efyh(dQfIUD`it8{Ft-ut(vp6x2R`rpa-oK)8sEwZDOlY$N?YgltEpPeNdLJ*t$kT1hw7LQOv{$GdKWWCETv3oiPETSIkF^R%|ibn?(0Cm*?$6&nG`lgGx>?OW`?5SC}<f9A~*_MQa|S7{outn%w(DOU}x32|w<=!jNn=$S!N1L*S|mCzqqT$?*3L0w`JgWgjgUKzmx9hmX4q4_PZ5)_LpQj;N^RaD8b8v_<>qvQ9nKaF`6nP2cHHrp$LrFX>;JW&RKD7~rzJgtj#$EJ<yZ5Aws_4&)T>)0V~&unCfgfi12cJUAilDEZRR&IZoD34XHa@?*;ZFAybwGbQXqyr1x6~W-rgJ60?<0tMqoe{!bC*2p|9V9pM@#9PptS;@IL<xiFA=-<1BGV&!Zhrh^;S@$3KI|#Kb$-@Q7hlhQHm+cZg5$V*)qw}cMjD{hFS-Y9LPByd39T=o=Z<;W>;ZnUZWXPJ{1F^aDM6qCwpW3_Fg?+U$RjKZB^kl7b9q^<^Rzf99MXx6bWWyu0-Mbf!jcUQj@pim6iZVgm*x^}QY#S*1=Zq;U1zOq?Ds<G;A`x@0n@k!SGE*!<wBCd;|r3)vpRJNeG&V9ALaO#)9!3?+9U43#L<hA$k4LbuHYtiN6X($aEhj~g0oN!F&jzY?HdG7kRt7ortLM0FC5u2!A6Ae1;GwS_5hRR(|zZQ(MLlbc{LP<di{!o=vxKXV(%ax=@JsSxYxvSZtB=KaCOCLM{8bU#0qE+m7$LCO(GkUwYV@YBx#l*W~&R~?!K*m9c)AcSAlTC@;}o;c9`lLrR~#FsBV>3p&Po+khc12+ZiKTG|~%aS?99xxh$qGWiPC*SD(_=O<d$|@MAKxF!5v5L@2B3Y^}8rrHSzj=OCe?8*3mc?0I(l&7ZiW8&$S~l{nI_AMb9|H^4qJ95ce95{}?eb2ik@=SCh*UqFrfue5la^nS&ofuaMg=Zru~*Nt%?rBF7SjuTm2j0x26GXD1;Sy5Eqor^ke)}-T1a{NM)Bp7XjDgNxYG36P={TuM{7I`!*Ly}B3!O0|4-202|KmRFQSN6KIQnZu87%3rk$$PNJJBdkTGQG@{Pt^w2$QP5ftlO@)ppq#hPg*_fQ+wF)@TlM6+nl}xmFrgPP1VRez9aLPS)Em~jO02myV$8A0C*IEF&Aj|ud?5vFc`A5+1B#a_9bbV8{=s_M<Qb5?_I|1n1nx7gC!#oSL)`wQrWa2ZF`gC_$+D-zgWZ9@;@$FuPDJM4u{&kz%cRDw}?bA_~Lh%YL+<{RbJv|{*1K6B~Q7+g}GT>5L*xhSV(18&_m~3so@81c<x9;S-y>gpeE1yPW}fw=i_;9<e3T`<zXY7X#9K)#fie`?UllVx9qx)G@4w`0xO2Eqf{_-lkjIaXt2d{kqTQtrr-X!%ZGBmC$cN2Cr}yF8R0Z0N+Srz5fFUBt8SpzokALYgQ~R6iclNDVUC(EQ#rgKnF>iOH+w@x!>dpF9!Z2Ae01tM7iX7n=i`u-Hmn?Kht=AhK=@#HPg7?z!2~Ky*BWjPme9CNBMK_%^PP`T2sT{N;S)%v<I>rVKG$`NRUQg(--0Yg?}MSRPSbiI?6t#S#F%?@F>EU&2Wl?3jaE%`(Sts`r<e_KpBH_UvbW$u)2+ttAA|VFd*<UPFZd*PaNx&=Sv-pugSyl8xt%Xn)hdpk&v5?aNHm`MKyx3-9(nwP+u!(jUbPqF#0giXCQS_~oZ=o!r&XJl_q)+3jxTElv-&6QJHO^)r->u_DNAoqs$TIZ0@vVCFm!K+O4;RUE{@yny$Z>-klp~vVgn?9<N;OISPKZR?VhCRCf`Vw<Bh-3;(&X5lt9s@`k6rHe6*GzI6QPCYmPQ{LyHxT31(y%5K-yf%oN<$JupqSQHzPRMDVS&oK!G`%Ff@uhY4spS(ubG_|#SAk6X2P9Ok09|1NG7Q!)6FfZ&+PqO19sQ$En&!Z@=@2>M*zj-FLMd>m#z>3C#AcQ!yzH3N;WTw^^-Gd_-tMfyI?_(^s|YZ;TNNI*|}4uR?i)hlGOu+z|9-y@2VTp%=!ttAUJ!g5YzqfFV)iUgx+&I1*jaGwV7>5Fkbkt>3OIO=9zjSbx@L^I!!gDShOZf6w_beSN`Y|?=)()+x*n^!t~9A-Z0Ky|&X+hX3sg+>4)ocSb#Do%wRJ*#}eahUm}1ItZI>17-4*O81bX_MjOJJ#GxP0Iu{bl~(<hi+Kq-HGXjrB8h)`qZ%T5TerFuZqB8Qg*&D4wLn#al!UOC!0+nrzB^}gJZQr0B$Vn@dL@jWTM9iTMwP(%XF2_zRNu{cp;nr*ukblr&~E0<)*lwp9((qs?*!5d=XRuth`#?UvK9(N??B>;UG2b3-D`UW1%zgSAWae`I&$!|08WS^8*1Lej)y@ZC=jK1bYgdl<lkr3T!2Gxye^EhmT;>ATYxbj+4h>+9%7}Xo)=PK3;yyima{5aX|&oBq*O4mM?=UP~3r+!4(oG_hnE;#JPMKR5Zf<DZj}K*>LV6r(pO9UZcn68Za$Kf=woAnmjeiM1wm}gW3m3nEt&mSru<$un)HN>9+9m6L9icIV)#?K&71PwEUOm=^*$-j|cYNIiCUH15QeRD5~r3Y4#`CL!zsAkY&Fn$5goP7zs~Z<Stbn<fMoT`L<3scOzhY1Wb-5`lG4~;fSSm+ss6UUUc+hfYxf}nLg;?oW6}__@!59p8I0}^5I_Yq%-LKbYp62A7DqG^lYTv*r($JdK{;FlVfTiek`bvLhW8q2&(_y-rTTMZ2N0*Z<-3+js+JThWovo4-Ynb-7n>v&&w<=^K_0KmY9HM+hZ_iy<>SnyA0;9^?1LR#cY6lbXnhR>uQtDu+3mfTj7~+mjP`*pnz3;GvD?KOk6KucZFlCIdGjcvnVo{;T~n0Z<oOat_{`{Gw!iOPc{DzgDG%jHGiw>_Rcw3XM$;ttp?NKh~*_%XD~gE;a<@F2~*~WAm`kLzF`+$R@-@ZVK5bLzP$)XKp>)*v=^i4kaO<E*mS?$%(V%VgH*HaK9rNc8DG)ab{)*n>)__xZXP!*?C)hRr<7c_q+QT+?K*GNo4{D}Z98yjU?Q-<&U}U+%;g*S=G=QG_u?!q)72cR&WjFG&9~=bIDMu=c_EuEF@w#x%Y2iI@k^Z*X}OwVo5AeAg7qP**J(KimFYToU#I1Aj;NCFnU3ULUXEX(&xYq8#8VHZ(s}h*aHH<S*rPIUkucmw6uz}~5e|8v5Kd18`J+l-UQOs2hB46&5zGVyG~w<(mIl@V6zOfxF(k|+SKoPEd<Ql0B^^Cph3H*rh-d53B-LcL7<OU#?sR<{#hNvy$vXj_-WZT}|A8{dV=~RC2jEmUqg=|A;GvE9UPerth-FiW0-8IRDS3yc{`8LJ4T%!XK?Un@H|ay|-Ap(@h5!ER%q%|1M(^|X&Uv-Upke2e*Y1xmax>rrBtqM%8|Sxbot4WXZDmtbB~>0QB7SVHP{~eABMXCLlSMSF_%{*>dnur?;{CrAvV@$0Zs(i1f(46@j0K18$PNYl3;54Bni3W=QS&H73=@4KcFHpla9!Y1?xkl|3UHJTPzt!Opnvpj;_LDXbHD^@k$}1~M?cYUCeHpEA)+`sLo}-IFh$^!8459OV;GZ}6J)CEH2d%uT&MT>`tRAYbuK!;T4=be>##W1?u{|>P@Bida%EgUHb@;=@Jo4<maVv+uBz3l$Z8dmPl9|~r?{(=I%Xvxvna3>jrGWfDZ#1#WqrL}%8o^QxV~xh*?p0hD^u$!(y)@_`3j^!n0vO2zKOB#BmKmT)`)=#vF}E;Ez-L0Ed4}~eFD)6Gc;ii1Er>MqBpA^X@E~UlzQBjGcxYVzOU8+#K&vF!+4`pxRmxDUO(<p*X@YZ;L_D)wlaf(+HOe26e2pB?`fG}5#X*R+Y6v#v@QONkr#)vALKic-MA42EyR-_UU{yzm6n2KdmLfy-)Y*&p7eL=W{fH#kNvy=3(Ug;b7@CaYmEjA0K4w9PE|TzyJqWY;k+dc^9kKy3x)sSdZPJ?&63bn-?Mq~!V$cWRh|E{D%&yf`A=%#9p;PFj+i~?=hE?d`C+FKw=XcwgY$mSC?Oqi_9Bx^&ev2ZyROONYdIo3?fx3WLQm&pp)F@Jl{2e1S=r`g_B5onN(QwV-CgykxSj3TC{nZqIWa^y-GZ_0I>S=I-Oz+=_jdN4`WVWDUWPkLGu%;H8M_zS>OWX480^(@b~_Bc1QznIWp&+{QDcny#Ht#W4C?L=YGxi7hruaS6x%}iSjB9mj@gell6uCM;zUi&$y79tBf*jJa_)~_zOYJgm{u)p;i6i8dqODdQxTH2+_#l&oXe{2<_f&~E322eI4nYlbh6wt)53dXa1_O<SYdxr+*hPKX@U;#@KHOw#uh48T9w{Ufa31-siJOgBU(`<qa%o_B3}&!Sp%b!IGbf-F#Q;Aq&j@mA6@GJ3#<+t{*0qKi>J7rN9jOIx-UI#SOC@t4uANp$`AG!w+W_LON}eDoIc+;U#e}na@gy@u%Ki*g4mh9Vdr_iEf}~S_9pU|N^ZM0U4HAP0EsVUMtdNHqe@t4NRSJq64?^^h7H%>xqlg_n7QaOV-Z$!RG-)?6j&A*IQkow2hS5FfklAt#l_nBvR!aVxxEOKEPlXkkBv>3ed{v-?gRfNNGhiO^#>XF?oPnzHZNA)n4Y<XrpA{{<_P1@BRg0Gc*qhl1uCqBXRX{|P2k)7<|eD<T-2U-sF*lt(s7P1RDP({oNs$u!4g5gyEq#|rxb?kkr=H<G7rKq!@R>eo-b)$URU3p(>h<>jz|jElX*}|k*Q}P9ToX*C3LymI&#Emb>FB^9QLRXdS8xFm>mi}#p?6>^D}{~@^V`?Sv!@<)iMRfYP-Wo;ClR+7B|j$C01|0wImk0ytVU3hnbdlu&fPmaa*o%jBCHUsJNaHEE)sb?XVfSVpTIJ19tIHX@nE$Q&r3sB~kUkOeiqbGOW>DBxoF4*&8op)(j@`nU>^-K={ZNLg#<<(;gpgH9Y#5kztU#Z-Y6ywosl5^|m5DDz@wJ6dt3$@7pSBm_GrBY57eKpVFG1WSS=?^a&y^QLvU*Ft)E>5FcztEjji>har!r9n<W4220Z#Cepz0IbdQ9j0a(YXM#yabV0XmoQwN9UFT3c#cU$fE*OUtrwtZNdf+R6UaS%0d!N5oPMeRXa-f7qVhF+5U;U^xLaz*71lEX7zmyTRrfVXO=P?GRK4`?Ji;!xv#v0M>7e#vSe5|%jR|E`89iqjfq8-+^GR$YZFT}4Swq!sq<zQhNh#VP9;0^=9Tt=3DPyZZ4A`_7p5z1F^JSUd_AQ8%Y*D?yEcuh1@5ox0rKPsM>R?F=6Qn!t?GLkjR+LDwXWdhp#vaQOo1@p-sa<!4+AB2H<h<B+hSw5?`O*?`VnUGvl1)Vk1hytg}#XYj61Dt8aL)od0v?dxc#!r^@eUUGBHy-!pKwC)YK8r^3=(Mi$d)bTr-Z{mk-p{2WVV(i#>vy-exJft33u+G=`ynsNBO~nPjMubC`yyuI)uE7Tj0R)4+Gl~>elLYcKus(6kcNpNDJ5t&m%eB0Blb5Mft)S-fw<1Qv_UmqBuo<OjS^THqJ+f{<HRueQfERRT^9L@-un1a9@pxl!2dBCps#=JGRb$<W+Pp<t6KQJ*}ZlXp?IK&2fYxD6kDzs%p9B*@^yzyG2)SPPm=&Ti~`hk=v<0*S~=%inF#6zEJJ?@2Toj63V;U9p<6Aql?@!xRd4gQdrA2<yUp74S{U1B+qTQBbUzH_l`Ni1V&15Z{55ZvcS1wSpP_5{d~9%x0E$tJY<HZ7LQ~LLVo0elrC{PPSAa^{zV$P4=^7>^$%7wv<D#&LmLtTrK8hcXts_eD;|*^bzwWyS9>E{R0b2ZRwUt|akW}{)-Y6>`>tE@pb9$|{6)YFZ>-6R(bN-OlIGIqz(FGHPdaHn=weuE{EfGuz*VVFG<%NbR(AH?6Xs^epm1(QD0wo)Ko(hdH8YB!B<V6dP{E|i#xV+WYh=QF2x=QAoZQ%^oRF_s!>GZ~3fCq~HptA|v2@FL004s&^h|L+`au$=evQ-R$r&pq;L+Bb;(W45>cGCyGBCY-0x`(YsY)~A|M@3Ym&@nQ$;Xh2L+Uhu{U+bu#p1>v4WS$<gW(pOiU8J+OEc)6rYUl(Dr1)`x=nz|Yu-z5?8d+n)f#_*@Tc>NaB#130j;|*kpjx+om?u`<u39$xxRU>syX>I`U5D$DQSxY-Bgt$jd(WOYQHam(@@}HZzvZ`0`h6GwC+D|6lYmouJ_1G8*(y8Kg&?b!+oqAP9|m0UBfZ%ze*BlRY3uD;mg#(yT@-#TtG)>FB2UW-`Qcuy4K$NFq94g%z;*@X9CbH}a5ZZ=%_mFiZhQ1H*UK4uR<1Vd>MlZCB^jbZqF+jf;Zi3l=POxROj39VmOT#Ex4md!-vil<>222Jx20@Ry^@vB?Y#ir=RgFw7vdllnU;=vG?@ybthVkKTo5(l@m#jmpXhxc@+(60v;#*!ao~f9?@QGU^-J$n9zM!*o-gZ4#?ZAf7|w7spS%ggbw1N^#vQ`9btaCu^i(^)6}yD^ojq#xm5{o650^v)ld;BQdGGsTsA2J-F@tSVmucIN4c~jX0w*H{qex-{)u{XxEm~wafbL^=(5Ua{{IblPvpN$O8b!j-4?TtkwV~BQ#`^TdibjF1s;cPs5AGj@%{mf4C$6b69Ah8?R=_7|`zod-Qj-B(CEqp7X^SQkB%?ApxoNYyl%C5~mg=J{#3_#T9+fv02o^d4pwEAzbL8u*3UQo_2UswZHw$BSf_Y>vgFc!y0P%zIOfS%<#F12dBoluzT`JxqRwppdT*Rt(I*C91FbB9_CsMj7Djz=X7{el_-su4WRQ*Ni>jO%WAsS)e2vHEJa8C2Oy;}+4e8_KF`hKNPYlC|m;25rK^%biDC{i8P-5>6QxUzd$UG6SSIk#3O5Rjp>@bok5$u;grrn(pdXG{_pU2<n<dv&yDRnysr_{0T79|mNv<8W&7NV)`@upkQVT;}U-(ZBJQFVVkWXSHw{KctOfF)FBuHg@Qt8$X`P39Fr82Embgu>oEfe&Q8sLt&w*S?pvx1XeqtCB;k0cuYK1S8o(0_;Q=Pl(53-T=@CG8oH{t!T=E4Y$Mq&>a5L#U)q5VlIwoIcL;FygVedAl3Rv!obTfp`eajqdt-;W=w6a^A>r=mcJB0R=iR*=i6xz^vfrKixCUN-{DLmfg{dO*V^RY&O4c;@!^3%^3Q4b(P-~TA;Y~lnuqx^@D~j>lDDw=~71vk&Og{?Xf<TH`IOtoPUPDgH0^eMLKJ_2rxbS4NkE=Ju{_;9Yzjdx%vp*Fi0l_?UM@%=rrsKu%rSD2?Y#ID2R<+>lc6~3%EZbzl2FXgKSYmO=u#&^2LAcRIf?d(++BZ?v+`}60BuAE(`9u5%yiRttMGMSDHyGES!vFbyjNk-)vm*fj"


def _products() -> list[dict[str, str | None]]:
    return json.loads(decompress(b85decode(_COMPRESSED_PRODUCTS)).decode("utf-8"))


def _decimal(value: str | None) -> Decimal | None:
    if not value:
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def _mm(value: str | None) -> Decimal | None:
    decimal_value = _decimal(value)
    return decimal_value * Decimal("10") if decimal_value is not None else None


def _dimension_text(product: dict[str, str | None]) -> str | None:
    dimensions = (product["length"], product["width"], product["height"])
    if not any(dimensions):
        return None
    return " x ".join(value or "-" for value in dimensions) + " cm"


def _get_or_create_category(
    session, name: str, parent_id: int | None, sort_order: int
) -> ProductCategory:
    statement = select(ProductCategory).where(
        ProductCategory.name == name,
        ProductCategory.parent_id == parent_id,
    )
    category = session.scalar(statement)
    if category is None:
        category = ProductCategory(
            name=name, parent_id=parent_id, sort_order=sort_order
        )
        session.add(category)
        session.flush()
    return category


def main() -> None:
    session = get_session_factory()()
    created = 0
    skipped = 0
    images_added = 0
    try:
        root = _get_or_create_category(session, ROOT_CATEGORY_NAME, None, 20)
        categories = {
            name: _get_or_create_category(session, name, root.id, index + 1)
            for index, name in enumerate(CATEGORY_ORDER)
        }

        for item in _products():
            product = session.scalar(
                select(Product).where(Product.sku == item["sku"])
            )
            if product is None:
                product = Product(
                    sku=item["sku"],
                    name=item["name"],
                    category_id=categories[item["category"]].id,
                    dimension_text=_dimension_text(item),
                    length_mm=_mm(item["length"]),
                    width_mm=_mm(item["width"]),
                    height_mm=_mm(item["height"]),
                    weight_kg=_decimal(item["weight"]),
                    unit="piece",
                    reference_price=_decimal(item["price"]),
                    currency_code="USD",
                    description=SOURCE_NOTE,
                    is_active=True,
                )
                session.add(product)
                session.flush()
                created += 1
            else:
                skipped += 1

            if not session.scalar(
                select(ProductImage.id).where(ProductImage.product_id == product.id)
            ):
                session.add(
                    ProductImage(
                        product_id=product.id,
                        image_url=f"{IMAGE_BASE_URL}/{item['sku']}.jpg",
                        is_primary=True,
                        sort_order=0,
                    )
                )
                images_added += 1

        session.commit()
        print(
            "Montessori materials import complete: "
            f"created={created}, skipped={skipped}, images_added={images_added}."
        )
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
