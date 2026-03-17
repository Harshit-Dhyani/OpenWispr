const fs = require('fs');
const path = require('path');

const rootDir = path.resolve(__dirname, '..');
const codexSkillsDir = path.join(rootDir, '.codex', 'skills');
const skillsDir = path.join(rootDir, 'skills');

function syncSkills() {
  console.log('Syncing skills from .codex/skills/ to skills/...');
  
  if (!fs.existsSync(codexSkillsDir)) {
    console.log('.codex/skills/ folder not found, skipping sync.');
    return;
  }
  
  if (!fs.existsSync(skillsDir)) {
    fs.mkdirSync(skillsDir, { recursive: true });
  }
  
  const skillFolders = fs.readdirSync(codexSkillsDir).filter(item => {
    const itemPath = path.join(codexSkillsDir, item);
    return fs.statSync(itemPath).isDirectory();
  });
  
  let synced = 0;
  
  for (const folder of skillFolders) {
    const skillFile = path.join(codexSkillsDir, folder, 'skill.md');
    
    if (fs.existsSync(skillFile)) {
      const destPath = path.join(skillsDir, `${folder}.md`);
      fs.copyFileSync(skillFile, destPath);
      console.log(`  Synced: ${folder}.md`);
      synced++;
    }
  }
  
  console.log(`Synced ${synced} skills.`);
}

syncSkills();
