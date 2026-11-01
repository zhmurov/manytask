# About Manytask

Manytask is an open-source platform for running programming courses. It brings
student repositories, automated testing, scores, and deadlines into one workflow,
while teachers choose the language, tools, and grading rules.

## How it works

1. Teachers maintain tasks, reference solutions, tests, and configuration in a
   private repository. The checker exports selected materials for students.
2. Manytask creates personal repositories for students. They write code and push
   their solutions using Git.
3. The course's CI runs the checker and reports scores to Manytask. Students and
   teachers can follow progress and deadlines in the web app.

See [Course as code](course_as_code.md) for the complete workflow, or start with
[the basic example](basic_example.md).

## GitLab and SourceCraft

Manytask supports both **GitLab** and **SourceCraft** as repository management
systems. Each deployment is configured for its chosen platform.

- **GitLab:** use GitLab authentication, student repositories, and CI pipelines.
- **SourceCraft:** students authenticate with Yandex ID. Manytask creates personal
  repositories from the course template and grants students access in the
  configured organization.

Authentication, repository organization, and CI settings differ between the
platforms. For example, SourceCraft branch protection is defined in repository
configuration rather than configured by Manytask through the API. Consult the
[concepts](concepts.md) and the
[deployment configurations](https://github.com/manytask/manytask/tree/main/compose)
when setting up your instance.

## Build your course

- **Your language and tools:** configure the checker to run your tests in the
  course's environment. See [checker configuration](checker_config.md).
- **Public and private materials:** choose which tasks, tests, and starter files
  are exported to students. See [repository structure](private_repo.md).
- **Scores and deadlines:** define task groups, points, and late-submission rules
  in [course configuration](manytask_yml_reference.md).
- **A starting point:** adapt the [reference course template](course_template.md).

## Join the project

The web app, checker, course template, review bot, and documentation are developed
in the [Manytask monorepo](https://github.com/manytask/manytask). Read the
[development guide](dev.md), explore
[open issues](https://github.com/manytask/manytask/issues), or join the
[community chat](https://t.me/manytask_chat).
