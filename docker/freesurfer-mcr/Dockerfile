FROM freesurfer/freesurfer:7.4.1

# Install Matlab Compiler Runtime R2019b (v97) required by segmentHA_T1/T2.
# The MCR is ~2 GB; it installs to /usr/local/freesurfer/MCRv97.
# fs_install_mcr is provided by FreeSurfer and handles the download.
RUN fs_install_mcr R2019b

# Smoke-test: the file FreeSurfer checks for at runtime
RUN test -f /usr/local/freesurfer/MCRv97/bin/glnxa64/libmwlaunchermain.so
