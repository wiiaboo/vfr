@echo on
vfr.py -i audio.flac -vf 24000/1001 test.avs --test > result-int-cfr-%1.txt
vfr.py -i audio.flac -vf 24/1.001 test.avs --test > result-float-cfr-%1.txt
vfr.py -i audio.flac -vt tc1-cfr.txt test.avs --test > result-tc1-cfr-%1.txt
vfr.py -i audio.flac -vt tc2-cfr.txt test.avs --test > result-tc2-cfr-%1.txt
vfr.py -i audio.flac -vt tc1-vfr.txt test.avs --test > result-tc1-vfr-%1.txt
vfr.py -i audio.flac -vt tc2-vfr.txt test.avs --test > result-tc2-vfr-%1.txt
@echo off
REM vfr.py -f 24/1.001 -c chap-fps-%1.txt -n chnames.txt test.avs
REM vfr.py -t tc1-cfr.txt -c chap-cfr-%1.xml -n chnames.txt test.avs
REM vfr.py -t tc1-vfr.txt -c chap-vfr-%1.xml -n chnames.txt test.avs