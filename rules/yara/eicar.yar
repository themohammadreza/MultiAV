rule EICAR_Test {
    meta:
        family = "EICAR"
        category = "test"

    strings:
        $a = "X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"

    condition:
        $a
}

