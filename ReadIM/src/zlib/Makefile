DEF = -D_LINUX

# CC = g++ -Wall $(DEF)
CC = gcc $(DEF)
ifdef DEBUG
CC += -g
endif

INC_D	= -I.. 

CODE = adler32.o compress.o deflate.o infblock.o infcodes.o inffast.o inflate.o inftrees.o infutil.o trees.o uncompr.o zutil.o

bufferlib:	$(CODE)
	exit

clean:
	exit

create:
	exit

dep:
	makedepend $(INC_D) $(DEF) *.c

%.o:
	$(CC) $(INC_D) -c -o $*.o $*.c
	@mkdir -p ../linux
	mv $*.o ../linux/$*.o




