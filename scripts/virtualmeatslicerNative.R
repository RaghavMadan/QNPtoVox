#Original code from https://github.com/IBIC/virtualPathology/bin/
# virtual slicer generates 0.5mm slices anterior to posterior
# Ensure the orientation of the image is correct as per the standard



library("RNifti")
library("png")

args=commandArgs(trailingOnly=TRUE)
if (length(args)==0) {
    stop("Usage: virtualmeatslicer.R subjectid")
} else {
    id=args[1]
}

brainfile <- paste(id, "X/",id,"_001_up_re.nii.gz", sep="")
print(brainfile)
brainnifti <- readNifti(brainfile)
braindata <- brainnifti[,,]

# Create folder name using id from argument
dir.create(paste(id, "_slices", sep=""))

# we go from maximum Y to minimum Y (anterior to positive) - find first slice with data

dims <- dim(braindata)
print(dims)
maxy <- dims[2]

# find the front and the back of the brain
foundbrain <- 0
front <- maxy -1
while (!foundbrain) {
    foundbrain <- sum(braindata[,front,])
    front <- front-1
}

foundbrain <- 0
back <-1
while (!foundbrain) {
    foundbrain <- sum(braindata[,back,])
    back <- back+1
}

#create sequence
n <- seq(front+1,back,by=-1)
print(n)

# write out images

rotate <- function(x) t(apply(x,2,rev))

for (i in 1:length(n)) {
    img <- braindata[,n[i],]
    img <- img/max(img)
    img <- rotate(rotate(rotate(img)))
    y <- dim(img)[2]
    # flip left and right
    img <- img[,c(y:1)]
    filename <- paste(id,"_slices/",id,"_s.", sprintf("%03d", n[i]) , ".png",sep="")
    writePNG(img, target=filename)
} 