pipeline {
    // Runs on the pod template labelled 'python-ci', which provides:
    //   - kaniko   : gcr.io/kaniko-project/executor (build & push, no Docker daemon)
    //   - helm     : alpine/helm (kubectl + helm available for k8s operations)
    agent { label 'python-ci' }

    environment {
        REGISTRY      = "git.19371928.xyz"
        BE_IMAGE_PATH = "automation/discord-snooker-backend"
        FE_IMAGE_PATH = "automation/discord-snooker-frontend"
        VITE_API_URL  = "https://snooker-1.automation.k8s.19371928.xyz"
        // Credential ID configured in Jenkins
        REGISTRY_CRED = "gitea-jenkins-token"    // Username+Password credential
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Detect Changes') {
            steps {
                script {
                    def changedFiles = sh(
                        script: 'git diff --name-only HEAD~1 HEAD 2>/dev/null || git diff --name-only $(git rev-list --max-parents=0 HEAD) HEAD',
                        returnStdout: true
                    ).trim()
                    echo "Changed files:\n${changedFiles}"

                    def backendPaths = ['backend/', 'engine/', 'db/', 'web.py', 'config.py', 'requirements.txt', 'Dockerfile.backend']
                    def frontendPaths = ['frontend/', 'Dockerfile.frontend']

                    env.BACKEND_CHANGED = changedFiles.split('\n').any { f ->
                        backendPaths.any { p -> f.startsWith(p) || f == p }
                    } ? 'true' : 'false'

                    env.FRONTEND_CHANGED = changedFiles.split('\n').any { f ->
                        frontendPaths.any { p -> f.startsWith(p) || f == p }
                    } ? 'true' : 'false'

                    echo "Backend changed: ${env.BACKEND_CHANGED}"
                    echo "Frontend changed: ${env.FRONTEND_CHANGED}"
                }
            }
        }

        stage('Set Tag') {
            steps {
                script {
                    env.TAG = sh(
                        script: 'date -u +"%Y%m%d-%H%M%S"',
                        returnStdout: true
                    ).trim()
                    env.BE_FULL_IMAGE = "${env.REGISTRY}/${env.BE_IMAGE_PATH}:${env.TAG}"
                    env.FE_FULL_IMAGE = "${env.REGISTRY}/${env.FE_IMAGE_PATH}:${env.TAG}"
                    echo "Backend image: ${env.BE_FULL_IMAGE}"
                    echo "Frontend image: ${env.FE_FULL_IMAGE}"
                }
            }
        }

        stage('Build & Push') {
            parallel {
                stage('Backend') {
                    when { expression { env.BACKEND_CHANGED == 'true' } }
                    steps {
                        container('kaniko') {
                            withCredentials([usernamePassword(
                                credentialsId: 'gitea-jenkins-token',
                                usernameVariable: 'REG_USER',
                                passwordVariable: 'REG_PASS'
                            )]) {
                                sh '''
                                    AUTH=$(printf "%s:%s" "$REG_USER" "$REG_PASS" | base64 -w 0)
                                    mkdir -p /kaniko/.docker
                                    printf '{"auths":{"%s":{"auth":"%s"}}}' \
                                        "$REGISTRY" "$AUTH" > /kaniko/.docker/config.json
                                '''
                                sh """
                                    /kaniko/executor \
                                        --context=dir://${env.WORKSPACE} \
                                        --dockerfile=${env.WORKSPACE}/Dockerfile.backend \
                                        --destination=${env.BE_FULL_IMAGE} \
                                        --cache=true \
                                        --cache-repo=${env.REGISTRY}/${env.BE_IMAGE_PATH}/cache
                                """
                            }
                        }
                    }
                }

                stage('Frontend') {
                    when { expression { env.FRONTEND_CHANGED == 'true' } }
                    steps {
                        container('kaniko') {
                            withCredentials([usernamePassword(
                                credentialsId: 'gitea-jenkins-token',
                                usernameVariable: 'REG_USER',
                                passwordVariable: 'REG_PASS'
                            )]) {
                                sh '''
                                    AUTH=$(printf "%s:%s" "$REG_USER" "$REG_PASS" | base64 -w 0)
                                    mkdir -p /kaniko/.docker
                                    printf '{"auths":{"%s":{"auth":"%s"}}}' \
                                        "$REGISTRY" "$AUTH" > /kaniko/.docker/config.json
                                '''
                                sh """
                                    /kaniko/executor \
                                        --context=dir://${env.WORKSPACE} \
                                        --dockerfile=${env.WORKSPACE}/Dockerfile.frontend \
                                        --build-arg VITE_API_URL=${env.VITE_API_URL} \
                                        --destination=${env.FE_FULL_IMAGE} \
                                        --cache=true \
                                        --cache-repo=${env.REGISTRY}/${env.FE_IMAGE_PATH}/cache
                                """
                            }
                        }
                    }
                }
            }
        }

        stage('Update k8s Manifests') {
            steps {
                script {
                    if (env.BACKEND_CHANGED == 'true') {
                        sh """
                            sed -i "s|${env.REGISTRY}/${env.BE_IMAGE_PATH}:[^ ]*|${env.BE_FULL_IMAGE}|g" \
                                k8s/backend.yaml
                        """
                        echo "k8s/backend.yaml updated to ${env.BE_FULL_IMAGE}"
                    }
                    if (env.FRONTEND_CHANGED == 'true') {
                        sh """
                            sed -i "s|${env.REGISTRY}/${env.FE_IMAGE_PATH}:[^ ]*|${env.FE_FULL_IMAGE}|g" \
                                k8s/frontend.yaml
                        """
                        echo "k8s/frontend.yaml updated to ${env.FE_FULL_IMAGE}"
                    }
                }
            }
        }

        stage('Deploy to Kubernetes') {
            when {
                expression { env.BACKEND_CHANGED == 'true' || env.FRONTEND_CHANGED == 'true' }
            }
            steps {
                container('helm') {
                    script {
                        if (env.BACKEND_CHANGED == 'true') {
                            sh "kubectl apply -f k8s/backend.yaml"
                            sh """
                                kubectl rollout status deployment/discord-snooker-backend \
                                    -n automation --timeout=120s
                            """
                        }
                        if (env.FRONTEND_CHANGED == 'true') {
                            sh "kubectl apply -f k8s/frontend.yaml"
                            sh """
                                kubectl rollout status deployment/discord-snooker-frontend \
                                    -n automation --timeout=120s
                            """
                        }
                    }
                }
            }
        }
    }

    post {
        success {
            script {
                def deployed = []
                if (env.BACKEND_CHANGED == 'true') deployed << env.BE_FULL_IMAGE
                if (env.FRONTEND_CHANGED == 'true') deployed << env.FE_FULL_IMAGE
                if (deployed) {
                    echo "Deployed: ${deployed.join(', ')}"
                } else {
                    echo "No components changed — nothing deployed."
                }
            }
        }
        failure {
            echo "Pipeline failed. Check logs above."
        }
    }
}
