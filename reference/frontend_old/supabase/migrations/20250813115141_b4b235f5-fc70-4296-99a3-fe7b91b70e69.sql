-- Step 1: Unlink chats from the test supergroups
UPDATE chats 
SET telegram_supergroup_id = NULL, telegram_sync = false 
WHERE telegram_supergroup_id IN (-1002693383546, -1002618114488, -1002554121378, -1002848008437, -1002245678432, -1002779635244, -1002598871574, -1002880892698);

-- Step 2: Delete members from the test supergroups
DELETE FROM telegram_group_members 
WHERE supergroup_id IN (-1002693383546, -1002618114488, -1002554121378, -1002848008437, -1002245678432, -1002779635244, -1002598871574, -1002880892698);

-- Step 3: Delete the test supergroups themselves
DELETE FROM telegram_supergroups 
WHERE id IN (-1002693383546, -1002618114488, -1002554121378, -1002848008437, -1002245678432, -1002779635244, -1002598871574, -1002880892698);