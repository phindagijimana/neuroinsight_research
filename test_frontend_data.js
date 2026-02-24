// Simulate frontend data processing
const normalizeStatus = (status) => {
  if (status === 'running') return 'processing';
  if (status === 'pending') return 'pending';
  if (status === 'completed') return 'completed';
  if (status === 'failed') return 'failed';
  return 'queued';
};

const toUiJob = (job) => {
  const normalizedStatus = normalizeStatus(job.status);
  return {
    id: job.id,
    filename: job.filename,
    status: normalizedStatus,
    progress: job.progress ?? 0,
    uploadedAt: job.created_at?.split('T')[0] || 'N/A',
    completedAt: job.completed_at?.split('T')[0] || null,
    currentStep: job.current_step ?? '',
    errorMessage: job.error_message || null
  };
};

// Test with actual API data
const testJobs = [
  {"id":"fix_test","filename":"fix_test.nii.gz","file_path":"/tmp/neuroinsight/uploads/bbce290e75d743e2b2521ee6ce50d18b_sub-01_T1w.nii.gz","status":"running","error_message":null,"created_at":"2026-01-23T06:32:40.779195","started_at":"2026-01-23T06:33:12.213966","completed_at":null,"result_path":null,"progress":136,"current_step":"Processing...(Intensity Normalization)","patient_name":null,"patient_id":null,"patient_age":null,"patient_sex":null,"scanner_info":null,"sequence_info":null,"notes":null,"visualizations":null}
];

console.log('Testing frontend data transformation:');
testJobs.forEach(job => {
  const uiJob = toUiJob(job);
  console.log('Original:', { id: job.id, status: job.status, progress: job.progress, current_step: job.current_step });
  console.log('UI Job:', { id: uiJob.id, status: uiJob.status, progress: uiJob.progress, currentStep: uiJob.currentStep });
  console.log('Should display progress?', uiJob.status === 'processing' || uiJob.status === 'pending');
  console.log('---');
});
