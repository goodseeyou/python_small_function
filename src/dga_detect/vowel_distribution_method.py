'''
Created on 2013/12/29

@author: Paul
'''
import sys
if __name__ == '__main__':
    vowels="aeiou"
    for line in sys.stdin:
        line=str(line).strip('\n').strip()
        tokens=line.rsplit('.')
        vowels_count=0
        desh_count=0
        char_count=0
        for i in range(len(tokens)-1):
            for achar in tokens[i]:
                if(achar in vowels):
                    vowels_count+=1
                if(achar=='-'):
                    desh_count+=1
                char_count+=1    
        vowel_ratio_nonvowel=float(vowels_count)/float(char_count-vowels_count-desh_count+1e-307)
        vowel_ratio_total =float(vowels_count)/float(char_count-desh_count+1e-307)
        print(str(vowel_ratio_nonvowel)+' '+str(vowel_ratio_total))