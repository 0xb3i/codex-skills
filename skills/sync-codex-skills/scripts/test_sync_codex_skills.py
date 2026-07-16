#!/usr/bin/env python3
import json
import tempfile
import unittest

import sync_codex_skills as sync


class SyncCodexSkillsTest(unittest.TestCase):
    def test_registers_managed_skill_by_direction(self):
        manifest = sync.empty_manifest()

        sync.register_skill(manifest, "push", "mistake-notebook", "~/dotfiles-codex", "user@example.com", "~/dotfiles-codex")
        sync.register_skill(manifest, "pull", "remote-only", "~/dotfiles-codex", "user@example.com", "~/dotfiles-codex")

        self.assertIn("mistake-notebook", manifest["local_to_remote"])
        self.assertIn("remote-only", manifest["remote_to_local"])

    def test_push_one_skill_then_updates_server(self):
        commands = sync.plan_commands(
            direction="push",
            skill="mistake-notebook",
            repo="~/dotfiles-codex",
            server="user@example.com",
            server_repo="~/dotfiles-codex",
            message="update mistake-notebook",
        )

        self.assertEqual(
            commands,
            [
                ["git", "-C", "~/dotfiles-codex", "add", "skills/mistake-notebook"],
                ["git", "-C", "~/dotfiles-codex", "commit", "-m", "update mistake-notebook"],
                ["git", "-C", "~/dotfiles-codex", "push", "-u", "origin", "HEAD"],
                ["ssh", "user@example.com", "cd ~/dotfiles-codex && git pull --ff-only"],
                ["ssh", "user@example.com", "mkdir -p ~/.codex/skills && test -e ~/.codex/skills/mistake-notebook || ln -s ~/dotfiles-codex/skills/mistake-notebook ~/.codex/skills/mistake-notebook"],
            ],
        )

    def test_pull_one_skill_commits_server_first(self):
        commands = sync.plan_commands(
            direction="pull",
            skill="mistake-notebook",
            repo="~/dotfiles-codex",
            server="user@example.com",
            server_repo="~/dotfiles-codex",
            message="update mistake-notebook from server",
        )

        self.assertEqual(commands[0][0], "ssh")
        self.assertIn("git add skills/mistake-notebook", commands[0][2])
        self.assertEqual(commands[-1], ["git", "-C", "~/dotfiles-codex", "pull", "--ff-only"])

    def test_dry_run_outputs_json_commands(self):
        output = sync.format_commands([["git", "status"]], dry_run=True)

        self.assertEqual(json.loads(output), [["git", "status"]])

    def test_auto_pushes_only_registered_local_to_remote_skill(self):
        manifest = sync.empty_manifest()
        sync.register_skill(manifest, "push", "mistake-notebook", "~/dotfiles-codex", "user@example.com", "~/dotfiles-codex")

        commands = sync.plan_auto_commands(manifest, "mistake-notebook", side="local", message="auto sync")

        self.assertEqual(commands[0], ["git", "-C", "~/dotfiles-codex", "add", "skills/mistake-notebook"])
        self.assertEqual(sync.plan_auto_commands(manifest, "untracked", side="local", message="auto sync"), [])

    def test_auto_remote_publishes_remote_to_local_skill(self):
        manifest = sync.empty_manifest()
        sync.register_skill(manifest, "pull", "remote-only", "~/dotfiles-codex", "user@example.com", "~/dotfiles-codex")

        commands = sync.plan_auto_commands(manifest, "remote-only", side="remote", message="auto sync")

        self.assertEqual(commands[0], ["git", "-C", "~/dotfiles-codex", "add", "skills/remote-only"])
        self.assertEqual(commands[-1], ["git", "-C", "~/dotfiles-codex", "push", "-u", "origin", "HEAD"])

    def test_auto_detects_remote_when_local_repo_is_absent(self):
        with tempfile.TemporaryDirectory() as server_repo:
            manifest = sync.empty_manifest()
            sync.register_skill(manifest, "pull", "remote-only", "/no/such/local/repo", "user@example.com", server_repo)

            commands = sync.plan_auto_commands(manifest, "remote-only", side="auto", message="auto sync")

            self.assertEqual(commands[0], ["git", "-C", server_repo, "add", "skills/remote-only"])


if __name__ == "__main__":
    unittest.main()
