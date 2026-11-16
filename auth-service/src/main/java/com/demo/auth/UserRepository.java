package com.demo.auth;

import java.util.Optional;

/** Minimal repository surface used by the demo agents. */
public interface UserRepository {
    Optional<User> findByEmail(String email);

    User save(User user);
}
