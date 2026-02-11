"""
PhaseMilestones—Fixedprogresspercentagesperpipelinephase.

Eachplugindefinesalistof(log_marker,percentage,label)tuples.
WhentheCeleryworkerseesalog_markerinthecontainer'sstdout,
itjumpsthejob'sprogresstothatfixedpercentage.

Thepercentagesareweightedestimatesbasedontypicalwall-clocktime
foreachphase.TheyareNOTcomputeddynamically—theyare
hand-tunedconstantsthatrepresent"howfarthroughthepipeline
arewe"whenagivenphaseisreached.

PhasesarematchedinORDER.Theworkercheckseachmarkeragainst
thelatestlogoutput.Onceamarkerismatched,progressjumpsto
thatpercentage(nevergoesbackwards).
"""

fromtypingimportDict,List,Tuple

#
#Type:Listof(log_marker_regex_or_substring,pct,label)
#
PhaseMilestone=Tuple[str,int,str]

#
#FreeSurferrecon-all(~6-8hours)
#
#Phasesandtheirtypicalwall-clockweight:
#autorecon1(motioncorrect,talairach,skullstrip)~15min->3%
#autorecon2(intensitynorm,whitematterseg,tessellate,
#smooth,inflate,register,parcellate)~4-5h->70%
#autorecon3(sphere,corticalthickness,stats)~1-2h->20%
#Post-processing(stats,bundleextraction)~10min->5%
#
FREESURFER_RECON:List[PhaseMilestone]=[
#Setup&inputvalidation
("recon-all",2,"Initializingrecon-all"),
("SUBJECTS_DIR",3,"Settingupsubjectdirectory"),

#autorecon1
("MotionCorrect",5,"Motioncorrection"),
("mri_convert",6,"Convertinginputformat"),
("Talairach",8,"Talairachregistration"),
("NUIntensityCorrection",10,"Intensitycorrection(N3)"),
("SkullStripping",14,"Skullstripping"),

#autorecon2
("EMRegister",18,"EMregistration"),
("CANormalize",20,"CAnormalize"),
("CARegister",25,"CAregister(atlas)"),
("SubCortSeg",30,"Subcorticalsegmentation"),
("IntensityNormalization2",33,"Intensitynormalization2"),
("WhiteMatterSegmentation",36,"Whitemattersegmentation"),
("Fill",38,"Fillingventricles"),
("Tessellate",42,"Tessellatinghemispheres"),
("Smooth1",45,"Smoothingsurface1"),
("Inflation1",48,"Inflatingsurface1"),
("QSphere",52,"Quasi-spheremapping"),
("FixTopology",56,"Fixingtopology"),
("MakeWhiteSurface",60,"Generatingwhitesurface"),
("Smooth2",63,"Smoothingsurface2"),
("Inflation2",65,"Inflatingsurface2"),
("SphericalMapping",68,"Sphericalmapping"),
("IpsilateralSurfaceReg",72,"Surfaceregistration"),
("CorticalParcellation",75,"Corticalparcellation(Desikan)"),
("PialSurface",78,"Generatingpialsurface"),

#autorecon3
("CorticalParcellation2",82,"Corticalparcellation(DKT)"),
("CorticalRibbon",85,"Corticalribbonmask"),
("CorticalThickness",88,"Computingcorticalthickness"),
("ParcellationStats",91,"Parcellationstatistics"),
("CorticalParcellation3",93,"Corticalparcellation(BA)"),
("WM/GMContrast",95,"WM/GMcontrast"),

#Completion
("recon-all.*finished",97,"recon-allfinished"),
("FreeSurferrecon-allcompleted",100,"Completed"),
]

#
#FastSurfer(~10-60mindependingonGPU/CPU)
#
#Phases:
#SegmentationCNN~1-5min->35%
#Surfacereconstruction~5-45min->50%
#Stats~2min->10%
#
FASTSURFER:List[PhaseMilestone]=[
#Setup
("run_fastsurfer",2,"StartingFastSurfer"),
("SUBJECTS_DIR",3,"Settingupdirectories"),

#Segmentation(CNN)
("RunningFastSurferCNN",5,"Loadingsegmentationmodel"),
("Loadingcheckpoint",8,"Loadingmodelcheckpoint"),
("Evaluating",12,"RunningCNNsegmentation"),
("sagittal",18,"Segmentingsagittalplane"),
("coronal",24,"Segmentingcoronalplane"),
("axial",30,"Segmentingaxialplane"),
("ViewAggregation",35,"Aggregatingviews"),

#Surfacereconstruction
("recon-surf",38,"Startingsurfacerecon"),
("mri_convert",40,"Convertingvolumes"),
("mris_inflate",50,"Inflatingsurfaces"),
("mris_sphere",58,"Sphericalmapping"),
("mris_register",65,"Surfaceregistration"),
("mris_ca_label",72,"Corticalparcellation"),
("mris_anatomical_stats",80,"Anatomicalstatistics"),
("mri_aparc2aseg",85,"aparc+asegcreation"),

#Stats&metrics
("aseg.stats",90,"Writingstatistics"),
("Metricsextracted",95,"Extractingmetrics"),

#Completion
("FastSurfercompleted",100,"Completed"),
]

#
#fMRIPrep(~2-6hours)
#
FMRIPREP:List[PhaseMilestone]=[
("fMRIPrep",2,"InitializingfMRIPrep"),
("Anatomicalprocessing",8,"Anatomicalpreprocessing"),
("Brainextraction",15,"Brainextraction"),
("Tissuesegmentation",22,"Tissuesegmentation"),
("Surfacereconstruction",35,"Surfacereconstruction"),
("BOLDprocessing",50,"BOLDpreprocessing"),
("Slice-timingcorrection",55,"Slice-timingcorrection"),
("Head-motionestimation",60,"Head-motionestimation"),
("Susceptibilitydistortion",65,"Susceptibilitydistortioncorrection"),
("Registration",72,"Registrationtostandard"),
("Confoundestimation",82,"Confoundestimation"),
("BOLDresampling",90,"BOLDresampling"),
("Generatingreport",95,"Generatingreport"),
("fMRIPrepfinished",100,"Completed"),
]

#
#Genericfallback(anyunknownplugin)
#Usessimpleelapsed-timefractionsofthemaxtime
#
GENERIC:List[PhaseMilestone]=[
("Starting",5,"Initializing"),
("Processing",25,"Processing"),
("Running",50,"Running"),
("Writing",75,"Writingoutputs"),
("completed",100,"Completed"),
]

#
#Registry:plugin_id->milestonelist
#
MILESTONES:Dict[str,List[PhaseMilestone]]={
"freesurfer_recon":FREESURFER_RECON,
"freesurfer_recon_long":FREESURFER_RECON,#samepipeline
"fastsurfer":FASTSURFER,
"fastsurfer_seg":FASTSURFER,
"fmriprep":FMRIPREP,
}

#Sharedsystemphases(prependedtoallplugins)
SYSTEM_PHASES:List[PhaseMilestone]=[
#ThesearesetbytheCelerytaskdirectly,notfromlogmarkers
]


def get_milestones(plugin_id: str) -> List[PhaseMilestone]:
    """Get phase milestones for a plugin, falling back to generic."""
    return MILESTONES.get(plugin_id, GENERIC)
