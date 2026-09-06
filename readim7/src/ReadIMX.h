//--------------------------------------------------------------------------------------------------
//
// Copyright (C) 2001-2013 LaVision GmbH.  All Rights Reserved.
//
//--------------------------------------------------------------------------------------------------

#ifndef __READIMX_H
#define __READIMX_H


#if defined _WIN32 || defined _WIN64

#include <windows.h>

#ifdef __BORLANDC__
#	define EXPORT	_export
#endif

#ifdef _MSC_VER
#	define EXPORT	__declspec(dllexport)
#endif

#define READ_IM7

#endif

#ifdef _LINUX
#	pragma message ("This is a Linux operating system")

#	include <stdlib.h>
#	include <string.h>
#       include <cstdlib>
#	define EXPORT

#endif
#	include <stdlib.h>
#	include <string.h>
#       include <cstdlib>

#include <stdio.h>


typedef enum
{
	IMREAD_ERR_NO = 0,	// no error
	IMREAD_ERR_FILEOPEN,	// cannot open file
	IMREAD_ERR_HEADER,	// error while reading the header
	IMREAD_ERR_FORMAT,	// file format not read by this DLL
	IMREAD_ERR_DATA,		// data reading error
	IMREAD_ERR_MEMORY,	// out of memory
	IMREAD_ERR_ATTRIBUTE_INVALID_TYPE,	// invalid attribute type
	IMREAD_ERR_ATTRIBUTE_NO_DATA,			// missing attribute data
} ImReadError_t;


typedef unsigned char      Byte;
typedef unsigned short int Word;

typedef struct
{
	float	factor;
	float offset;
	char	description[16];
	char	unit[16];
} BufferScaleType;

enum BufferFormat_t 
{
	BUFFER_FORMAT__NOTUSED		= -1,			// not used any longer
	BUFFER_FORMAT_MEMPACKWORD	= -2,			// memory packed Word buffer (= byte buffer)
	BUFFER_FORMAT_FLOAT			= -3,			// float image
	BUFFER_FORMAT_WORD			= -4,			// word image
	BUFFER_FORMAT_DOUBLE			= -5,			// double image
	BUFFER_FORMAT_FLOAT_VALID	= -6,			// float image with flags for valid pixels
	BUFFER_FORMAT_IMAGE			= 0, 			//	image with unspecified data format (word, float or double)
	BUFFER_FORMAT_VECTOR_2D_EXTENDED,		//	PIV vector field with header and 4*2D field
	BUFFER_FORMAT_VECTOR_2D,		   		//	simple 2D vector field
	BUFFER_FORMAT_VECTOR_2D_EXTENDED_PEAK,	//	same as 1 + peak ratio
	BUFFER_FORMAT_VECTOR_3D,	   			//	simple 3D vector field
	BUFFER_FORMAT_VECTOR_3D_EXTENDED_PEAK,	//	PIV vector field with header and 4*3D field + peak ratio
   BUFFER_FORMAT_COLOR 			= -10, 		// base of color types
	BUFFER_FORMAT_RGB_MATRIX	= -10, 		// RGB matrix from color camera (Imager3)
	BUFFER_FORMAT_RGB_32			= -11	 		// each pixel has 32bit RGB color info
};

/// @brief Buffer structure of ReadIMX library.
typedef struct
{
   int         isFloat;
   int         nx,ny,nz,nf;
   int         totalLines;
	int			vectorGrid;			// 0 for images
	int			image_sub_type;	// BufferFormat_t
    float*   floatArray;
    Word*    wordArray;
	BufferScaleType	scaleX;		// x-scale
	BufferScaleType	scaleY;		// y-scale
	BufferScaleType	scaleI;		// intensity scale
	bool*			bMaskArray;			// mask array, NULL if no mask exists
} BufferType;

/// @brief Attribute list structure of ReadIMX library.
typedef struct AttributeList
{
   char*          name;
   char*          value;
   AttributeList* next;
} AttributeList;

enum	Image_t	// type in header of IMX files
	{	IMAGE_IMG 			= 18,	 	// uncompressed WORD image
		IMAGE_IMX,						// compressed WORD image
		IMAGE_FLOAT,            	// floating point uncompressed
		IMAGE_SPARSE_WORD,			// sparse buffer with word scalars
		IMAGE_SPARSE_FLOAT,			// sparse buffer with float scalars
		IMAGE_PACKED_WORD,			// memory packed word buffer with one byte per pixel
	};

Byte* Buffer_GetRowAddrAndSize( BufferType* myBuffer, int theRow, unsigned long &theRowLength );
int  CreateBuffer( BufferType* myBuffer, int theNX, int theNY, int theNZ, int theNF, int isFloat, int vectorGrid, BufferFormat_t imageSubType );
void SetBufferScale( BufferScaleType* theScale, float theFactor, float theOffset, const char* theDesc, const char* theUnit );

//! Get number of components for a given vector type (BUFFER_FORMAT_VECTOR_x).
int GetVectorComponents( BufferFormat_t imageSubType );

//! Destroy the data structure creacted by ReadIMX().
void DestroyBuffer( BufferType* myBuffer );
void DestroyAttributeList( AttributeList** myList );
//! Append a new attribute to the list.
int SetAttribute( AttributeList** myList, const char* theName, const char* theValue );

void WriteScalesAsAttributes( FILE* theFile, const BufferType& p_pBuffer );
void WriteAttribute_END( FILE *theFile );

int ReadImgAttributes( FILE* theFile, AttributeList** myList );
int WriteImgAttributes( FILE* theFile, bool isIM6, AttributeList* myList );

ImReadError_t SCPackOldIMX_Read( FILE* theFile, BufferType* myBuffer );

int WriteIMX( FILE *theFile, BufferType* myBuffer );


// Read file of type IMG/IMX/VEC, returns error code ImReadError_t
int ReadIMX ( const char* theFileName, BufferType* myBuffer, AttributeList** myList );

// Write file of type IMG or IMX, returns error code ImReadError_t
int WriteIMG( const char* theFileName, BufferType* myBuffer );
int WriteIMGX( const char* theFileName, bool isIMX, BufferType* myBuffer );
int WriteIMGXAttr( const char* theFileName, bool isIMX, BufferType* myBuffer, AttributeList* myList );



#endif //__READIMX_H
