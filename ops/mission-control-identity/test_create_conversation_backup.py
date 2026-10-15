from pathlib import Path
import unittest
class BackupChecks(unittest.TestCase):
 def test_guarded_backup(self):
  s=(Path(__file__).parent/'create-conversation-backup.sh').read_text()
  for x in ('--network none','--read-only','--cap-drop ALL','--cap-add FOWNER','--cap-add CHOWN','create_backup','BACKUP_MAGIC','resume','conversation_backup_completed=true','live_state_replaced=false'): self.assertIn(x,s)
  for x in ('docker rename','docker volume rm','docker pull','--privileged'): self.assertNotIn(x,s)
 def test_manual_workflow(self):
  w=(Path(__file__).parents[2]/'.github/workflows/mission-control-conversation-backup.yml').read_text()
  for x in ('workflow_dispatch:','APPROVE_CONVERSATION_BACKUP','create-conversation-backup.sh','healthz'): self.assertIn(x,w)
if __name__=='__main__': unittest.main()
