"""The laboratory exception never broadens the existing main signing gate."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ci_release as release


class LabSigningTests(unittest.TestCase):
    def env(self):
        branch = "refs/heads/lab/v4.0.1-speech-preroll"
        return dict(GITHUB_ACTIONS="true", GITHUB_EVENT_NAME="push", GITHUB_REF=branch,
                    GITHUB_REPOSITORY="Dmitrijsmok/BYDMate", GITHUB_ACTOR="Dmitrijsmok",
                    GITHUB_TRIGGERING_ACTOR="Dmitrijsmok", GITHUB_REF_PROTECTED="true",
                    GITHUB_WORKFLOW_REF=f"Dmitrijsmok/BYDMate/.github/workflows/ci.yml@{branch}")

    def test_exact_owner_protected_branch_push_is_accepted(self):
        release.require_trusted_lab_push(self.env())

    def test_lab_is_not_accepted_by_main_gate(self):
        with self.assertRaises(release.Failure):
            release.require_trusted_push(self.env())

    def test_each_guard_is_required(self):
        for key in self.env():
            env = self.env()
            env[key] = "untrusted"
            with self.subTest(key=key), self.assertRaises(release.Failure):
                release.require_trusted_lab_push(env)

    def test_pull_requests_and_arbitrary_branches_are_rejected(self):
        for event in ("pull_request", "pull_request_target", "workflow_dispatch"):
            with self.subTest(event=event), self.assertRaises(release.Failure):
                release.require_trusted_lab_push(dict(self.env(), GITHUB_EVENT_NAME=event))
        for branch in ("main", "lab/other", "lab/v4.0.1-speech-preroll-evil"):
            with self.subTest(branch=branch), self.assertRaises(release.Failure):
                release.require_trusted_lab_push(dict(self.env(), GITHUB_REF=f"refs/heads/{branch}"))

    def test_repository_identity_is_the_exact_experiment(self):
        info = release.read_build_info(Path(__file__).resolve().parents[2])
        self.assertEqual("4.0.1-asr-lab.1", info.version_name)
        self.assertEqual(100002, info.version_code)
        self.assertEqual("BYDMate-dilink3-v4.0.1-asr-lab.1.apk", info.apk_name)


if __name__ == "__main__":
    unittest.main()
